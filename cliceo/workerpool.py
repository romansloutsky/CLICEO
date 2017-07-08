import sys
import psutil
import multiprocessing
from multiprocessing.managers import SyncManager
import signal
from ctypes import c_bool
from functools import partial
from tblib import pickling_support
from .controller import CLIcontrollerBase


def _call_worker_in_worker_proc(task_arg):
  return globals()['worker'](task_arg)


class Worker(object):
  def __init__(self,work_callable,permission_to_proceed,sleep_lock,
               ready_to_die_queue,PIDcleanup):
    self.callable = work_callable
    self.proceed = permission_to_proceed
    self.sleep_lock = sleep_lock
    self.ready_to_die_queue = ready_to_die_queue
    self.PIDcleanup = PIDcleanup
  
  def __call__(self,arg):
    if self.proceed.value:
      try:
        result = self.callable(arg)
        self.PIDcleanup()
      except Exception:
        result = sys.exc_info()
        # Automagically allow pickling traceback details for returning them to
        # pool manager, allowing manager to raise error with correct traceback
        pickling_support.install()
      return result
    else:
      # Signal to pool manager readiness to be terminated
      self.ready_to_die_queue.get()
      self.ready_to_die_queue.task_done()
      # Sleep until terminated by waiting to acquire lock
      self.sleep_lock.acquire()


def init_process_to_ignore_SIGINT():
  signal.signal(signal.SIGINT,signal.SIG_IGN)

class PoolManager(object):
  def __init__(self,work_doer,numproc=None,**kwargs):
    self.shared_resources_manager = SyncManager()
    self.shared_resources_manager.start(initializer=init_process_to_ignore_SIGINT)
    self.permission = self.shared_resources_manager.Value(c_bool,True)
    self.sleep_lock = self.shared_resources_manager.Lock()
    self.sleep_lock.acquire() # Workers will sleep by waiting to acquire lock
    self.ready_to_die_queue = self.shared_resources_manager.JoinableQueue()
    if isinstance(work_doer,type) and issubclass(work_doer,CLIcontrollerBase):
      self.PIDregistry = self.shared_resources_manager.dict()
      
      def registerPID(PID):
        self.PIDregistry[multiprocessing.current_process().name] = PID
      
      work_callable = work_doer.partial(PIDpublisher=registerPID,**kwargs)
    else:
      work_callable = partial(work_doer,**kwargs)
    
    def unregisterPID():
      try:
        self.PIDregistry.pop(multiprocessing.current_process().name)
      except:
        pass
    
    worker = Worker(work_callable,self.permission,self.sleep_lock,
                    self.ready_to_die_queue,unregisterPID)
    
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
              proc.kill()
        except OSError:
          pass
    self.ready_to_die_queue.join()
  
  def __call__(self,sequence_to_map):
    '''
    Sequence order will not be preserved!
    '''
    try:
      results = self.proc_pool.imap_unordered(_call_worker_in_worker_proc,
                                              sequence_to_map)
      for r in results:
        if isinstance(r,tuple) and len(r) == 3 and issubclass(r[0],Exception):
          raise r[0],r[1],r[2] # Exception type, value, traceback
        else:
          yield r
    except:
      self.announce_shutdown()
      self.cleanup_workers()
      self.proc_pool.terminate()
      raise
    finally:
      self.proc_pool.close()
      self.proc_pool.join()
      self.shared_resources_manager.shutdown()
