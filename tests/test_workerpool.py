import unittest
import os
import subprocess
from multiprocessing import pool
from itertools import cycle
from tempfile import template as TEMPFILE_TEMPLATE
from mock import patch,mock_open,PropertyMock,Mock,call,DEFAULT
import contextlib2
from cliceo import workerpool,controller


class TestError(Exception):
  pass


@patch('multiprocessing.Manager')
class test_Worker(unittest.TestCase):
  def prepare_IPC_mocks(self,patchedManagerCallable):
    mocks = {}
    mockManager = patchedManagerCallable.return_value
    permission_value = PropertyMock(return_value=True)
    permission = mockManager.Value.return_value
    type(permission).value = permission_value
    mocks['permission'] = permission
    mocks['permission_value'] = permission_value
    mocks['sleep_lock'] = mockManager.Lock.return_value
    mocks['ready_to_die_queue'] = mockManager.JoinableQueue.return_value
    return mocks
  
  def test_successful_calling(self,patchedManagerCallable):
    mocks = self.prepare_IPC_mocks(patchedManagerCallable)
    mock_work_callable = Mock(side_effect=['result%d' % i for i in [1,2,3]])
    mock_PIDcleanup = Mock()
    
    worker = workerpool.Worker(mock_work_callable,mocks['permission'],
                               mocks['sleep_lock'],mocks['ready_to_die_queue'],
                               mock_PIDcleanup)
    results = [worker('dummyarg%d' % i) for i in [1,2,3]]
    
    self.assertItemsEqual(mocks['permission_value'].call_args_list,
                          [call() for i in xrange(3)])
    self.assertItemsEqual(mock_PIDcleanup.call_args_list,
                          [call() for i in xrange(3)])
    self.assertItemsEqual(mock_work_callable.call_args_list,
                          [call('dummyarg%d' % i) for i in [1,2,3]])
    self.assertItemsEqual(results,['result%d' % i for i in [1,2,3]])
  
  def test_not_allowed_to_proceed(self,patchedManagerCallable):
    mocks = self.prepare_IPC_mocks(patchedManagerCallable)
    mocks['permission_value'].return_value = False
    mock_work_callable = Mock()
    mock_PIDcleanup = Mock()
    
    worker = workerpool.Worker(mock_work_callable,mocks['permission'],
                               mocks['sleep_lock'],mocks['ready_to_die_queue'],
                               mock_PIDcleanup)
    worker('arg')
    
    self.assertItemsEqual(mock_PIDcleanup.call_args_list,[])
    self.assertItemsEqual(mock_work_callable.call_args_list,[])
    mocks['permission_value'].assert_called_once_with()
    mocks['ready_to_die_queue'].get.assert_called_once_with()
    mocks['ready_to_die_queue'].task_done.assert_called_once_with()
    mocks['sleep_lock'].acquire.assert_called_once_with()
  
  def test_work_doer_raises_exception(self,patchedManagerCallable):
    mocks = self.prepare_IPC_mocks(patchedManagerCallable)
    mock_work_callable = Mock(side_effect=TestError)
    mock_PIDcleanup = Mock()
    
    worker = workerpool.Worker(mock_work_callable,mocks['permission'],
                               mocks['sleep_lock'],mocks['ready_to_die_queue'],
                               mock_PIDcleanup)
    r1,r2,_ = worker('arg')
    
    self.assertItemsEqual(mock_PIDcleanup.call_args_list,[])
    mock_work_callable.assert_called_once_with('arg')
    self.assertIs(r1,TestError)
    self.assertTrue(isinstance(r2,TestError))


@patch('subprocess.Popen')
@patch('cliceo.tempdir.TemporaryWorkingDirectory')
@patch('__builtin__.open',new_callable=mock_open)
class test_PartializedControllerCallable(unittest.TestCase):
  def test_basic_call(self,patched_open,patched_TWD,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycallable = workerpool.PartializedControllerCallable(
                                                  controller.CommandLineCaller,
                                                             'dummy_callstr')
    dummycontroller = dummycallable()
    patched_Popen.assert_called_once_with('dummy_callstr',
                                          stdout=dummycontroller.stdout,
                                          stderr=dummycontroller.stderr,
                                          shell=True)
  
  def test_call_w_PIDpublisher(self,patched_open,patched_TWD,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    mockPIDpublisher = Mock()
    dummycallable = workerpool.PartializedControllerCallable(
                                                  controller.CommandLineCaller,
                                                             'dummy_callstr')
    dummycontroller = dummycallable(PIDpublisher=mockPIDpublisher)
    mockPIDpublisher.assert_called_once_with(patched_Popen.return_value.pid)
  
  def test_execution_in_tempdir(self,patched_open,patched_TWD,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycallable = workerpool.PartializedControllerCallable(
                                                  controller.CommandLineCaller,
                                                             'dummy_callstr')
    dummycontroller = dummycallable(in_tmpdir=True,tmpdir_loc='/desired/loc')
    patched_TWD.assert_called_once_with(dir='/desired/loc',
                                        prefix=TEMPFILE_TEMPLATE,suffix='')
  
  def test_STDIN_and_STDERR_capture(self,patched_open,patched_TWD,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycallable = workerpool.PartializedControllerCallable(
                                                  controller.CommandLineCaller,
                                                             'dummy_callstr',
                                                           capture_stdout=True)
    dummycontroller = dummycallable(capture_stderr=True)
    self.assertEqual(dummycontroller.captured_stdout,'dummySTDOUT')
    self.assertEqual(dummycontroller.captured_stderr,'dummySTDERR')
    patched_Popen.assert_called_once_with('dummy_callstr',
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE,
                                          shell=True)
  
  def test_STDIN_and_STDERR_silencing(self,patched_open,patched_TWD,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycallable = workerpool.PartializedControllerCallable(
                                                  controller.CommandLineCaller,
                                                               'dummy_callstr')
    dummycontroller = dummycallable(silence_stdout=True,silence_stderr=True)
    patched_open.assert_called_once_with(os.devnull,'w')
    patched_Popen.assert_called_once_with('dummy_callstr',
                                          stdout=patched_open.return_value,
                                          stderr=patched_open.return_value,
                                          shell=True)
  
  def test_STDIN_and_STDERR_redirection(self,patched_open,patched_TWD,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycallable = workerpool.PartializedControllerCallable(
                                                  controller.CommandLineCaller,
                                                               'dummy_callstr')
    dummycontroller = dummycallable(err_to_out=True)
    self.assertIs(dummycontroller.stderr,subprocess.STDOUT)
    patched_Popen.assert_called_once_with('dummy_callstr',stdout=None,
                                          stderr=subprocess.STDOUT,shell=True)


class TestController(controller.CommandLineCaller):
  call_count = 0
  
  @classmethod
  def attach_classmethods(cls,run_before_CLIcall=None,run_after_CLIcall=None):
    if run_before_CLIcall is not None:
      setattr(cls,'run_before_CLIcall',classmethod(run_before_CLIcall))
    if run_after_CLIcall is not None:
      setattr(cls,'run_after_CLIcall',classmethod(run_after_CLIcall))
  
  @classmethod
  def set_callnum_to_raise_exception(cls,raise_on):
    cls.raise_on_call_number = raise_on
  
  def __init__(self,callvalue,run_before_CLIcall=None,run_after_CLIcall=None,
               raise_on=None,**kwargs):
    self.attach_classmethods(run_before_CLIcall,run_after_CLIcall)
    self.set_callnum_to_raise_exception(raise_on)
    controller.CommandLineCaller.__init__(self,
                                          'call with %s' % str(callvalue),
                                          **kwargs)
  
  @classmethod
  def update_call_count(cls):
    cls.call_count += 1
    if cls.call_count == cls.raise_on_call_number:
      raise TestError
  
  def call(self):
    self.update_call_count()
    if hasattr(self,'run_before_CLIcall'):
      self.run_before_CLIcall(self)
    controller.CommandLineCaller.call(self)
    if hasattr(self,'run_after_CLIcall'):
      self.run_after_CLIcall(self)


class AllWorkersSleeping(Exception):
  pass

# Utility function imitates the distribution of arguments from sequence to map
# out to workers by cycling over "workers" (dicts representing global state of
# worker processes), checking whether the worker has gone to sleep by calling
# sleep_lock.acquire(), and assigning the argument to the next awake worker.
# If all workers are asleep, as should eventually happen when shutdown is
# announced by PoolManager, AllWorkersSleeping is raised notifying upstream
# that ready_to_die_queue.join() success can now be imitated.
def cycling_worker_assigner(worker_num_cycler,mocks,outer_worker_fxn,seq_to_map):
  for item in seq_to_map:
    curr_worker = None
    while curr_worker != mocks['current_worker']:
      curr_worker = worker_num_cycler.next()
    for _ in xrange(mocks['workerpool']._processes):
      next_worker = worker_num_cycler.next()
      if mocks['worker_global_dicts'][next_worker]['sleeping']:
        mocks['globals_fxn']()
        continue
      else:
        break
    else:
      raise AllWorkersSleeping
    mocks['last_item_assigned_to_worker'] = item
    yield outer_worker_fxn(item)

@contextlib2.contextmanager
def patched_multiproc_setup():
  with patch('__builtin__.globals') as patched_globals_fxn:
    mocks = {'globals_fxn':patched_globals_fxn}
    with patch('signal.signal') as patched_signal_action_setter:
      mocks['signal_action_setter'] = patched_signal_action_setter
      with patch('multiprocessing.Pool') as patchedPoolCallable:
        mock_worker_pool = Mock(spec=pool.Pool) #Actual Pool class
        
        # Several steps in initializing the multiproc mocking setup must happen
        # on instantiation of a worker pool, once the number of requested
        # workers becomes known
        def Pool_call_side_effect(numproc,initializer,initargs):
          (real_worker,) = initargs
          mocks['worker_global_dicts'] = [{'num':i,'sleeping':False}
                                          for i in xrange(numproc)]
          worker_cycler = cycle(mocks['worker_global_dicts'])
          # Setting side effect of globals() call during call to Pool (which
          # only happens once per call to this context manager) allows us to
          # inject cycling over the correct number of "workers"
          def globals_call_side_effect():
            workerglobaldict = worker_cycler.next()
            mocks['current_worker'] = workerglobaldict['num']
            return workerglobaldict
          mocks['globals_fxn'].side_effect = globals_call_side_effect
          # Now, each time the initializer calls globals(), a different dict
          # will be returned and a unique Mock will be placed into each dict.
          # Even though all the Mocks wrap the same real_worker object, calls
          # to that object from different "workers" can be tracked separately.
          for _ in xrange(numproc):
            mockworker = Mock(wraps=real_worker)
            initializer(mockworker)
          mock_worker_pool.configure_mock(**{'_processes':numproc})
          # When a "worker" calls sleep_lock.acquire(), the 'sleeping' flag in
          # that worker's globals dict will be set to True. Setting this side
          # effect during call to Pool happens AFTER the PoolManager object
          # acquires the lock for itself, thereby rendering it un-acquirable by
          # workers and assuring they sleep forever waiting to acquire it.
          def sleep_lock_acquire_side_effect():
            mocks['worker_global_dicts'][mocks['current_worker']]['sleeping'] = True
          mocks['sleep_lock'].acquire.side_effect = sleep_lock_acquire_side_effect
          return mock_worker_pool
        
        patchedPoolCallable.side_effect = Pool_call_side_effect
        mocks['PoolCallable'] = patchedPoolCallable
        mocks['workerpool'] = mock_worker_pool
        
        def mock_imap_side_effect(outer_worker_fxn,seq_to_map):
          # Call to imap_unordered happens after pool initialization, so
          # mock_worker_pool._processes will have been set to numproc in call
          # to Pool_call_side_effect()
          worker_num_cycler = cycle(xrange(mock_worker_pool._processes))
          return cycling_worker_assigner(worker_num_cycler,mocks,
                                         outer_worker_fxn,seq_to_map)
        
        mocks['workerpool'].imap_unordered.side_effect = mock_imap_side_effect
        with patch('cliceo.workerpool.SyncManager') as patchedSyncManager:
          mockManager = patchedSyncManager.return_value
          permission_value = PropertyMock(return_value=True)
          def permission_value_access_side_effect(*args):
            # PropertyMock gets called with no argument when the value is checked
            # and with one argument when the value is set. So, if an argument is
            # received, the PropertyMock's return_value is set to that argument.
            if args:
              permission_value.return_value = args[0]
            # Returning special value DEFAULT from the mock module from
            # side_effect causes the Mock object (and its variants) to return
            # the object's return_value
            return DEFAULT
          permission_value.side_effect = permission_value_access_side_effect
          permission = mockManager.Value.return_value
          type(permission).value = permission_value
          mocks['permission'] = permission
          mocks['permission_value'] = permission_value
          mocks['sleep_lock'] = mockManager.Lock.return_value
          mocks['ready_to_die_queue'] = mockManager.JoinableQueue.return_value
           
          # When PoolManager tries to join the ready_to_die_queue, the
          # asynchronous nature of the worker pool is imitated by continuing to
          # assign arguments to "workers" using cycling_worker_assigner() until
          # all workers have had a chance to notice the shutdown announcement
          # and go to sleep
          def ready_to_die_queue_join_side_effect():
            reached_unassigned = False
            remaining_seq_to_map = []
            # *** Test method must insert seq_to_map into mocks! ***
            for item in mocks['seq_to_map']:
              if item == mocks['last_item_assigned_to_worker']:
                reached_unassigned = True
                continue
              if reached_unassigned:
                remaining_seq_to_map.append(item)
            nprocsxrange = xrange(mocks['workerpool']._processes)
            remaining_seq_to_map.extend(nprocsxrange)
            try:
              for _ in cycling_worker_assigner(cycle(nprocsxrange),mocks,
                                        workerpool._call_worker_in_worker_proc,
                                               remaining_seq_to_map):
                pass
            except AllWorkersSleeping:
              # *** Test method must insert this testing callable into mocks! ***
              mocks['verify_shutdown_to_this_point']()
          
          mocks['ready_to_die_queue'].join.side_effect = \
                                            ready_to_die_queue_join_side_effect
          mocks['PIDregistry'] = mockManager.dict.return_value
          with patch('subprocess.Popen') as patchedPopen:
            child_p = patchedPopen.return_value
            child_p.communicate.return_value = ('dummy_stdout_obj',
                                                'dummy_stderr_obj')
            pid_value = PropertyMock()
            type(child_p).pid = pid_value
            mocks['Popen'] = patchedPopen
            mocks['child_p'] = child_p
            mocks['pid_value'] = pid_value
            yield mocks


class test_successful_parallel_execution_with_PoolManager(unittest.TestCase):
  
  @patch('cliceo.workerpool.partial')
  def test_execution_with_arbitrary_callable(self,patched_partial):
    NUMPROC = 3
    CALLSEQ = [0,1,2,3,4,5]
    def dummy_work_doer(arg):
      pass
    with patched_multiproc_setup() as mocks:
      poolmanager = workerpool.PoolManager(dummy_work_doer,CALLSEQ,numproc=NUMPROC,
                                           dummy_arg_to_partial='dummy_arg')
      patched_partial.assert_called_once_with(dummy_work_doer,
                                              dummy_arg_to_partial='dummy_arg')
      
      dummy_work_doer = patched_partial.return_value
      mocks['PoolCallable'].assert_called_once()
      self.assertItemsEqual(mocks['workerpool'].imap_unordered.call_args_list,
                            [])
      self.assertItemsEqual(dummy_work_doer.call_args_list,[])
      self.assertItemsEqual(mocks['permission_value'].call_args_list,[])
      self.assertItemsEqual(mocks['PIDregistry'].__setitem__.call_args_list,[])
      self.assertItemsEqual(mocks['PIDregistry'].pop.call_args_list,[])
      
      [r for r in poolmanager()]
      
      mocks['workerpool'].imap_unordered.assert_called_once_with(
                            workerpool._call_worker_in_worker_proc,CALLSEQ)
      self.assertItemsEqual(dummy_work_doer.call_args_list,
                            [call(i) for i in CALLSEQ])
      self.assertItemsEqual(mocks['permission_value'].call_args_list,
                            [call() for i in CALLSEQ])
      for i,d in enumerate(mocks['worker_global_dicts']):
        self.assertItemsEqual(d['worker'].call_args_list,
                              [call(j) for j in [v for v in CALLSEQ
                                                 if v % NUMPROC == i % NUMPROC]])
      mocks['workerpool'].close.assert_called_once_with()
      mocks['workerpool'].join.assert_called_once_with()
      # Under normal execution to completion a single call to
      # sleep_lock.acquire() is expected
      mocks['sleep_lock'].acquire.assert_called_once_with()
      # No calls to PIDregistry were expected because there is no PID tracking
      # for arbitrary callables
      self.assertItemsEqual(mocks['PIDregistry'].__setitem__.call_args_list,[])
      self.assertItemsEqual(mocks['PIDregistry'].pop.call_args_list,[])
  
  @patch('cliceo.workerpool.multiprocessing.current_process',
         **{'return_value.name':'dummyProc'})
  def test_execution_with_CLIcontroller(self,patched_curr_proc):
    NUMPROC = 3
    CALLSEQ = range(NUMPROC)
    def test_CLIcontroller_before_call(cls,controller_instance):
      self.assertTrue(callable(controller_instance.PIDpublisher))
      self.assertFalse(hasattr(controller_instance,'captured_stdout'))
      self.assertFalse(hasattr(controller_instance,'captured_stderr'))
    
    def test_CLIcontroller_after_call(cls,controller_instance):
      self.assertEqual(controller_instance.captured_stdout,'dummy_stdout_obj')
      self.assertEqual(controller_instance.captured_stderr,'dummy_stderr_obj')
    
    with patched_multiproc_setup() as mocks:
      poolmanager = workerpool.PoolManager(TestController,CALLSEQ,numproc=NUMPROC,
                             run_before_CLIcall=test_CLIcontroller_before_call,
                               run_after_CLIcall=test_CLIcontroller_after_call,
                                           err_to_out=True,capture_stdout=True)
      self.assertItemsEqual(mocks['Popen'].call_args_list,[])
      self.assertItemsEqual(mocks['PIDregistry'].__setitem__.call_args_list,[])
      self.assertItemsEqual(mocks['PIDregistry'].pop.call_args_list,[])
      
      mocks['pid_value'].side_effect = ['dummyPID%d' % i for i in CALLSEQ]
      [r for r in poolmanager()]
      
      for i,d in enumerate(mocks['worker_global_dicts']):
        self.assertItemsEqual(d['worker'].call_args_list,
                              [call(j) for j in [v for v in CALLSEQ
                                                 if v % NUMPROC == i % NUMPROC]])
      self.assertItemsEqual(mocks['Popen'].call_args_list,
                            [call('call with %d' % i,stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,shell=True)
                             for i in CALLSEQ])
      self.assertItemsEqual(mocks['pid_value'].call_args_list,
                            [call() for i in CALLSEQ])
      self.assertItemsEqual(mocks['PIDregistry'].__setitem__.call_args_list,
                            [call('dummyProc','dummyPID%d' % i)
                             for i in CALLSEQ])
      self.assertItemsEqual(mocks['PIDregistry'].pop.call_args_list,
                            [call('dummyProc') for i in CALLSEQ])
      mocks['workerpool'].close.assert_called_once_with()
      mocks['workerpool'].join.assert_called_once_with()


class test_exception_handling_by_Worker_and_PoolManager(unittest.TestCase):
   
  def verify_shutdown_announced_and_all_workers_went_to_sleep(self,mocks):
    numproc = mocks['workerpool']._processes
    nprocsxrange = xrange(numproc)
     
    # PoolManager should have done these
    self.assertItemsEqual(mocks['ready_to_die_queue'].put.call_args_list,
                            [call(None) for _ in nprocsxrange])
    self.assertIs(mocks['permission'].value,False)
     
    # Each worker should have done these
    self.assertItemsEqual(mocks['ready_to_die_queue'].get.call_args_list,
                            [call() for _ in nprocsxrange])
    self.assertItemsEqual(mocks['ready_to_die_queue'].task_done.call_args_list,
                            [call() for _ in nprocsxrange])
    self.assertItemsEqual(mocks['sleep_lock'].acquire.call_args_list,
                            [call() for _ in xrange(numproc+1)])
                                             # Additional call made by PoolManager
   
  def verify_pool_termination_closure_and_joining(self,mocks):
      # Pool should be terminated, closed, and joined on any error-caused shutdown
      mocks['workerpool'].terminate.assert_called_once_with()
      mocks['workerpool'].close.assert_called_once_with()
      mocks['workerpool'].join.assert_called_once_with()
   
  def test_arbitrary_callable_all_worker_halt_on_error_encountered_by_one(self):
    NUMPROC = 4
    CALLSEQ = [0,1,2,3,4,5]
    dummy_work_doer = Mock(side_effect=[0,1,2,TestError,4,5])
     
    with patched_multiproc_setup() as mocks:
      poolmanager = workerpool.PoolManager(dummy_work_doer,CALLSEQ,numproc=NUMPROC)
      # Since an arbitrary callable was used, not a CommandLineCaller instance,
      # poolmanager.PIDregistry should not have been created
      self.assertFalse(hasattr(poolmanager,'PIDregistry'))
      mocks['seq_to_map'] = CALLSEQ
      mocks['verify_shutdown_to_this_point'] = workerpool.partial(
            self.verify_shutdown_announced_and_all_workers_went_to_sleep,mocks)
      with self.assertRaises(TestError):
        [r for r in poolmanager()]
      mocks['ready_to_die_queue'].join.assert_called_once_with()
      self.assertItemsEqual(mocks['PIDregistry'].values.call_args_list,[])
      self.verify_pool_termination_closure_and_joining(mocks)
   
  @patch('psutil.Process')
  def test_CLIcontroller_all_worker_halt_on_error_encountered_by_one(self,
                                                                patchedPsutil):
    top_proc = patchedPsutil.return_value
    child_procs = [Mock(),Mock(),Mock()]
    top_proc.children.return_value = child_procs
    
    NUMPROC = 4
    CALLSEQ = [0,1,2,3,4,5]
     
    with patched_multiproc_setup() as mocks:
      mocks['PIDregistry'].values.return_value = ['dummyPID']
      poolmanager = workerpool.PoolManager(TestController,CALLSEQ,numproc=NUMPROC,
                                           err_to_out=True,capture_stdout=True,
                                           raise_on=3)
      self.assertTrue(hasattr(poolmanager,'PIDregistry'))
      mocks['seq_to_map'] = CALLSEQ
      mocks['verify_shutdown_to_this_point'] = workerpool.partial(
            self.verify_shutdown_announced_and_all_workers_went_to_sleep,mocks)
      with self.assertRaises(TestError):
        [r for r in poolmanager()]
      mocks['ready_to_die_queue'].join.assert_called_once_with()
      mocks['PIDregistry'].values.assert_called_once_with()
      patchedPsutil.assert_called_once_with(pid='dummyPID')
      top_proc.children.assert_called_once_with(recursive=True)
      for proc in [top_proc]+child_procs:
        proc.kill.assert_called_once_with()
      mocks['ready_to_die_queue'].join.assert_called_once_with()
      self.verify_pool_termination_closure_and_joining(mocks)


class test_PoolManager_execution_with_labels(unittest.TestCase):
  
  def test_successful_execution_with_labeled_input(self):
    NUMPROC = 3
    CALLSEQ = [0,1,2,3,4,5]
    LABELS = [str(i) for i in CALLSEQ]
    LABELEDCALLSEQ = zip(LABELS,CALLSEQ)
    dummy_work_doer = Mock(side_effect=[10*i for i in CALLSEQ])
    
    with patched_multiproc_setup() as mocks:
      poolmanager = workerpool.PoolManager(dummy_work_doer,LABELEDCALLSEQ,
                                           numproc=NUMPROC,labeled_items=True)
      results = [r for r in poolmanager()]
      self.assertItemsEqual(results,zip(LABELS,[10*i for i in CALLSEQ]))
    
  def test_halt_on_error_with_labeled_input(self):
    NUMPROC = 3
    CALLSEQ = [0,1,2,3,4,5]
    LABELS = [str(i) for i in CALLSEQ]
    LABELEDCALLSEQ = zip(LABELS,CALLSEQ)
    dummy_work_doer = Mock(side_effect=[TestError if i==3 else 10*i
                                        for i in CALLSEQ])
    
    with patched_multiproc_setup() as mocks:
      poolmanager = workerpool.PoolManager(dummy_work_doer,LABELEDCALLSEQ,
                                           labeled_items=True,numproc=NUMPROC)
      with self.assertRaises(TestError):
        mocks['seq_to_map'] = CALLSEQ
        [r for r in poolmanager()]
      self.assertTrue(hasattr(poolmanager,'error_on_label'))
      self.assertEqual(poolmanager.error_on_label,'3')


class DummyController(controller.CommandLineCaller):
  def __init__(self,val,**kwargs):
    self.val = val
    controller.CommandLineCaller.__init__(self,'sleep 0.01',**kwargs)
  
  def call(self):
    controller.CommandLineCaller.call(self)
    self.newval = self.val+100

class test_PoolManager_integration_with_multiprocessing_Pool(unittest.TestCase):
    
  def test_integration_using_seq_item_numbering(self):
    poolmanager = workerpool.PoolManager(DummyController,xrange(10),2,
                                         number_seq_items=True)
    for label,result in poolmanager():
      self.assertEqual(label+100,result.newval)
    
  def test_integration_using_arbitrary_labels(self):
    poolmanager = workerpool.PoolManager(DummyController,
                                         ((str(i+200),i) for i in xrange(10)),2,
                                         labeled_items=True)
    for label,result in poolmanager():
      self.assertEqual(eval(label)-100,result.newval)
    
