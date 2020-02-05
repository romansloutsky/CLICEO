import os
import subprocess
from . import contextmanagers


class CommandLineCaller(object):
  '''
  Intended to be used as base class for concrete command line controller classes
  for specific command line programs. Provides management of CLI exectution
  context via CLIcontextManager.
  
  Initialization parameters:
    :param callstr: String to be passed to subprocess.Popen() to be executed at
                    the command line
                    No default value -- a call string must be provided at
                    initialization
    :param PIDpublisher: Callable for reporting the PID of launched process
    
    Temporary working directory control:
      :param in_tmpdir: Boolean flag indicating whether a TemporaryWorkingDirectory
                        should be created for the duration of execution
      :param tmpdir_loc: Location where temporary directory should be created
                         If None, directory is created at the temporary location
                         specified by the OS
                         Ignored if in_tmpdir evaluates to False
    
    STDOUT/STDERR control:
      :param capture_stdout: Boolean flag indicating whether the STDOUT output
                             of created process should be captured
                             If True, output is stored as attribute
                             'captured_stdout'
      :param silence_stdout: Boolean flag indicating whether the STDOUT output
                             of created process should be redirected to os.devnull
                             Ignored if capture_stdout evaluates to True
      :param err_to_out: Boolean flag indicating whether STDERR output of created
                         process should be redirected to STDOUT (2>&1)
      :param capture_stderr: Boolean flag indicating whether the STDERR output
                             of created process should be captured
                             If True, output is stored as attribute
                             'captured_stderr'
                             Ignored if err_to_out evaluates to True
      :param silence_stderr: Boolean flag indicating whether the STDERR output
                             of created process should be redirected to os.devnull
                             Ignored if either err_to_out or capture_stdout
                             evaluate to True

  '''
  
  @classmethod
  def get_CLI_context_manager(cls):
    return contextmanagers.CLIcontextManager()
  
  def __init__(self,callstr,PIDpublisher=None,in_tmpdir=False,tmpdir_loc=None,
                    capture_stdout=False,silence_stdout=False,
                    err_to_out=False,capture_stderr=False,silence_stderr=False):
    self.callstr = callstr
    self.PIDpublisher = PIDpublisher
    self.tmpdir = in_tmpdir
    self.tmpdir_loc = tmpdir_loc
    self.cliCM = self.get_CLI_context_manager()
    
    self.stdout = subprocess.PIPE if capture_stdout else False if silence_stdout\
                                                                      else None
    if err_to_out:
      self.stderr = subprocess.STDOUT
    else:
      self.stderr = subprocess.PIPE if capture_stderr else False if silence_stderr\
                                                                      else None
  
  def _run(self,callstr):
    child_p = subprocess.Popen(callstr,stdout=self.stdout,stderr=self.stderr,
                               shell=True)
    if callable(self.PIDpublisher):
      self.PIDpublisher(child_p.pid)
    self.captured_stdout,self.captured_stderr = child_p.communicate()
  
  def call(self):
    '''
    This method runs inside the CLI context and passes the call from __call__()
    to _run().
    
    Deriving classes should extend this method with any activities that must
    be performed inside the CLI context before and/or after the call to _run()
    '''
    self._run(self.callstr)
  
  def __call__(self):
    if self.tmpdir:
      self.tmpdir = self.cliCM.enter_tmpdir(self.tmpdir_loc)
    
    if self.stdout is False or self.stderr is False:
      devnull = open(os.devnull,'w')
      self.cliCM.push(devnull)
      if self.stdout is False:
        self.stdout = devnull
      if self.stderr is False:
        self.stderr = devnull
    
    with self.cliCM:
      return self.call()

