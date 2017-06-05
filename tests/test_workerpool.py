import unittest
from mock import patch,PropertyMock
import contextlib2
from cliceo import workerpool,controller


class TestError(Exception):
  pass


class TestController(controller.CLIcontrollerBase):
  _command = 'ls'
  
  def call(self):
    if hasattr(self,'run_before_CLIcall'):
      self.run_before_CLIcall()
    controller.CLIcontrollerBase.call(self)
    if hasattr(self,'run_after_CLIcall'):
      self.run_after_CLIcall()
  
  @classmethod
  def do(cls,raise_on_call_number,*args,**kwargs):
    if cls.call_count == raise_on_call_number:
      raise TestError
    else:
      cls.call_count += 1
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
    return controller.CLIcontrollerBase.partial.__func__(cls,
                                                 raise_on_call_number=raise_on,
                                                         **kwargs)


@contextlib2.contextmanager
def patched_multiproc_setup(return_shared_objects=False):
  with patch('__builtin__.globals') as patched_globals_fxn:
    with patch('multiprocessing.Pool') as patchedPoolCallable:
      with patch('multiprocessing.Manager') as patchedManagerCallable:
        pool = patchedPoolCallable.return_value
        mocks = {'globals_fxn':patched_globals_fxn,'pool':pool,
                 'PoolCallable':patchedPoolCallable}
        if return_shared_objects:
          mockManager = patchedManagerCallable.return_value
          permission_value = PropertyMock(return_value=True)
          permission = mockManager.Value.return_value
          type(permission).value = permission_value
          mocks['permission'] = permission
          mocks['permission_value'] = permission_value
          mocks['sleep_lock'] = mockManager.Lock.return_value
          mocks['ready_to_die_queue'] = mockManager.JoinableQueue.return_value
          mocks['PIDregistry'] = mockManager.dict.return_value
        yield mocks


@contextlib2.contextmanager
def mock_in_worker_proc(work_doer,return_shared_objects=False,**kwargs):
  worker = {}
  def Pool_call_side_effect(numproc,initializer,initargs):
    actual_worker, = initargs
    worker['worker'] = actual_worker
  with patched_multiproc_setup(return_shared_objects) as mocks:
    mocks['PoolCallable'].side_effect = Pool_call_side_effect
    workerpool.PoolManager(work_doer,**kwargs)
    patched_globals_fxn = mocks.pop('globals_fxn')
    patched_globals_fxn.return_value = worker['worker']
    mocks['globals_dict'] = worker
    yield mocks
