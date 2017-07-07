import unittest
from multiprocessing import pool
from itertools import cycle
from mock import patch,PropertyMock,Mock,call
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


class TestController(controller.CLIcontrollerBase):
  _command = 'ls'
  
  def call(self):
    if hasattr(self,'run_before_CLIcall'):
      self.run_before_CLIcall(self)
    controller.CLIcontrollerBase.call(self)
    if hasattr(self,'run_after_CLIcall'):
      self.run_after_CLIcall(self)
  
  @classmethod
  def do(cls,*args,**kwargs):
    cls.call_count += 1
    if cls.call_count == cls.raise_on_call_number:
      raise TestError
    else:
      # Calling the underlying function of the bound classmethod allows us to
      # pass the class we want -- this class -- but still call the base class'
      # classmethod
      return controller.CLIcontrollerBase.do.__func__(cls,*args,**kwargs)
  
  @classmethod
  def partial(cls,run_before_CLIcall=None,run_after_CLIcall=None,raise_on=None,
              **kwargs):
    if run_before_CLIcall is not None:
      setattr(cls,'run_before_CLIcall',classmethod(run_before_CLIcall))
    if run_after_CLIcall is not None:
      setattr(cls,'run_after_CLIcall',classmethod(run_after_CLIcall))
    cls.call_count = 0
    cls.raise_on_call_number = raise_on
    return controller.CLIcontrollerBase.partial.__func__(cls,**kwargs)


@contextlib2.contextmanager
def patched_multiproc_setup():
  with patch('__builtin__.globals') as patched_globals_fxn:
    mocks = {'globals_fxn':patched_globals_fxn}
    with patch('signal.signal') as patched_signal_action_setter:
      mocks['signal_action_setter'] = patched_signal_action_setter
      with patch('multiprocessing.Pool') as patchedPoolCallable:
        mock_worker_pool = Mock(spec=pool.Pool) #Actual Pool class
        
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
          for item in seq_to_map:
            yield outer_worker_fxn(item)
        mocks['workerpool'].imap_unordered.side_effect = mock_imap_side_effect
        with patch('multiprocessing.Manager') as patchedManagerCallable:
          mockManager = patchedManagerCallable.return_value
          permission_value = PropertyMock(return_value=True)
          permission = mockManager.Value.return_value
          type(permission).value = permission_value
          mocks['permission'] = permission
          mocks['permission_value'] = permission_value
          mocks['sleep_lock'] = mockManager.Lock.return_value
          mocks['ready_to_die_queue'] = mockManager.JoinableQueue.return_value
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
    def dummy_work_doer(mocks):
      pass
    with patched_multiproc_setup() as mocks:
      poolmanager = workerpool.PoolManager(dummy_work_doer,numproc=NUMPROC,
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
      
      [r for r in poolmanager(CALLSEQ)]
      
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
      self.assertFalse(hasattr(controller_instance,'collected_stdout'))
      self.assertFalse(hasattr(controller_instance,'collected_stderr'))
    
    def test_CLIcontroller_after_call(cls,controller_instance):
      self.assertEqual(controller_instance.collected_stdout,'dummy_stdout_obj')
      self.assertEqual(controller_instance.collected_stderr,'dummy_stderr_obj')
    
    with patched_multiproc_setup() as mocks:
      poolmanager = workerpool.PoolManager(TestController,numproc=NUMPROC,
                             run_before_CLIcall=test_CLIcontroller_before_call,
                               run_after_CLIcall=test_CLIcontroller_after_call,
                                           err_to_out=True,capture_stdout=True)
      self.assertItemsEqual(mocks['Popen'].call_args_list,[])
      self.assertItemsEqual(mocks['PIDregistry'].__setitem__.call_args_list,[])
      self.assertItemsEqual(mocks['PIDregistry'].pop.call_args_list,[])
      
      mocks['pid_value'].side_effect = ['dummyPID%d' % i for i in CALLSEQ]
      [r for r in poolmanager(CALLSEQ)]
      
      for i,d in enumerate(mocks['worker_global_dicts']):
        self.assertItemsEqual(d['worker'].call_args_list,
                              [call(j) for j in [v for v in CALLSEQ
                                                 if v % NUMPROC == i % NUMPROC]])
      import subprocess
      self.assertItemsEqual(mocks['Popen'].call_args_list,
                            [call('ls',stdout=subprocess.PIPE,
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
