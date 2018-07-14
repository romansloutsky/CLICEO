import sys
import psutil
import multiprocessing
from multiprocessing.managers import SyncManager
import signal
from ctypes import c_bool
from functools import partial
import contextlib2
from tblib import pickling_support
from .controller import CommandLineCaller


def _call_worker_in_worker_proc(task_arg):
  return globals()['worker'](task_arg)


class LabeledObject(object):
  def __init__(self,label,obj,is_result=False):
    self.label = label
    self.obj = obj
    self.is_result = is_result
  
  @property
  def result(self):
    if self.is_result:
      return self.obj
    else:
      raise ValueError('This is not a result')
  
  @classmethod
  def _reapply_label(cls,label,result):
    return cls(label,result,is_result=True)
  
  def reapply_label_to_result(self,result):
    return self._reapply_label(self.label,result)
  
  @staticmethod
  def do_nothing(obj):
    return obj
  
  @classmethod
  @contextlib2.contextmanager
  def strip_label(cls,obj):
    if isinstance(obj,cls):
      if obj.is_result:
        raise ValueError('This is not a result')
      else:
        yield obj.obj,obj.reapply_label_to_result
    else:
      yield obj,cls.do_nothing

def LabeledObjectsSequence(sequence_of_label_item_pairs):
  for label,item in sequence_of_label_item_pairs:
    yield LabeledObject(label,item)

class Worker(object):
  def __init__(self,work_callable,permission_to_proceed,sleep_lock,
               ready_to_die_queue,PIDcleanup=None):
    self.callable = work_callable
    self.proceed = permission_to_proceed
    self.sleep_lock = sleep_lock
    self.ready_to_die_queue = ready_to_die_queue
    self.PIDcleanup = PIDcleanup
  
  def __call__(self,arg):
    if self.proceed.value:
      with LabeledObject.strip_label(arg) as (argval,reapply_label):
        try:
          result = self.callable(argval)
          if self.PIDcleanup is not None:
            self.PIDcleanup()
        except Exception:
          result = sys.exc_info()
          # Automagically allow pickling traceback details for returning them to
          # pool manager, allowing manager to raise error with correct traceback
          pickling_support.install()
        return reapply_label(result)
    else:
      # Signal to pool manager readiness to be terminated
      self.ready_to_die_queue.get()
      self.ready_to_die_queue.task_done()
      # Sleep until terminated by waiting to acquire lock
      self.sleep_lock.acquire()


def init_process_to_ignore_SIGINT():
  signal.signal(signal.SIGINT,signal.SIG_IGN)

def registerPID(PIDregistry,PID):
  PIDregistry[multiprocessing.current_process().name] = PID

class PoolManager(object):
  def __init__(self,work_doer,numproc=None,**kwargs):
    self.shared_resources_manager = SyncManager()
    self.shared_resources_manager.start(initializer=init_process_to_ignore_SIGINT)
    self.permission = self.shared_resources_manager.Value(c_bool,True)
    self.sleep_lock = self.shared_resources_manager.Lock()
    self.sleep_lock.acquire() # Workers will sleep by waiting to acquire lock
    self.ready_to_die_queue = self.shared_resources_manager.JoinableQueue()
    
    if isinstance(work_doer,type) and issubclass(work_doer,CommandLineCaller):
      self.PIDregistry = self.shared_resources_manager.dict()
      work_callable = work_doer.partial(PIDpublisher=partial(registerPID,
                                                             self.PIDregistry),
                                        **kwargs)
    
      def unregisterPID():
        try:
          self.PIDregistry.pop(multiprocessing.current_process().name)
        except KeyError:
          pass
      
      worker = Worker(work_callable,self.permission,self.sleep_lock,
                      self.ready_to_die_queue,unregisterPID)
    else:
      work_callable = partial(work_doer,**kwargs)
      worker = Worker(work_callable,self.permission,self.sleep_lock,
                      self.ready_to_die_queue)
    
    def init_worker_process(worker):
      # Proper handling to KeyboardInterrupt achieved by having workers ignore
      # it and deferring to the main process to handle everything, including
      # worker shutdown.
      # See: http://noswap.com/blog/python-multiprocessing-keyboardinterrupt
      init_process_to_ignore_SIGINT()
      globals()['worker'] = worker
    
    self.proc_pool = multiprocessing.Pool(numproc,initializer=init_worker_process,
                                          initargs=(worker,))
  
  def announce_shutdown(self):
    for _ in xrange(self.proc_pool._processes):
      self.ready_to_die_queue.put(None)
    self.permission.value = False
    # In case some of the processes have run out of things to do, give each
    # a dummy task to make sure they check the permission flag, detect that it's
    # False, and signal readiness to die via ready_to_die_queue
    self.proc_pool.imap_unordered(_call_worker_in_worker_proc,
                                (i for i in xrange(self.proc_pool._processes)))
  
  def cleanup_workers(self):
    if hasattr(self,'PIDregistry'):
      for pid in self.PIDregistry.values():
        try:
          top_proc = psutil.Process(pid=pid)
          children = top_proc.children(recursive=True)
          for proc in [top_proc]+children:
            try:
              proc.kill()
            except psutil.NoSuchProcess:
              pass
        except psutil.NoSuchProcess:
          pass
    self.ready_to_die_queue.join()
  
  def __call__(self,sequence_to_map,labeled_items=False,
                    number_seq_items=False):
    '''
    Sequence order will not be preserved!
    '''
    if labeled_items and number_seq_items:
      raise ValueError("Only one of 'labeled_items' and 'number_seq_items' "\
                       "may be true")
    elif labeled_items:
      sequence_to_map = LabeledObjectsSequence(sequence_to_map)
    elif number_seq_items:
      sequence_to_map = LabeledObjectsSequence(enumerate(sequence_to_map))
    try:
      results = self.proc_pool.imap_unordered(_call_worker_in_worker_proc,
                                              sequence_to_map)
      for r in results:
        rval = r.result if isinstance(r,LabeledObject) else r
        if isinstance(rval,tuple) and len(rval) == 3 and issubclass(rval[0],
                                                                    Exception):
          if isinstance(r,LabeledObject):
            self.error_on_label = r.label
          raise rval[0],rval[1],rval[2] # Exception type, value, traceback
        else:
          yield (r.label,rval) if isinstance(r,LabeledObject) else r
    except:
      self.announce_shutdown()
      self.cleanup_workers()
      self.proc_pool.terminate()
      raise
    finally:
      self.proc_pool.close()
      self.proc_pool.join()
      self.shared_resources_manager.shutdown()
