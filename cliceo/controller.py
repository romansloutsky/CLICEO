import os
import subprocess
from functools import partial
from . import contextmanagers


class CommandLineCaller(object):
  
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
  
  @classmethod
  def do(cls,*args,**kwargs):
    caller = cls(*args,**kwargs)
    caller()
    return caller
  
  @classmethod
  def partial(cls,*args,**kwargs):
    return partial(cls.do,*args,**kwargs)


class SimpleGenericCLIcontroller(CommandLineCaller):
  
  _command = ''
  
  @property
  def command(self):
    '''
    Name of command to be executed at the command line
    
    Deriving classes should override class attribute _command with the commands
    they drive
    '''
    return self._command
  
  _option_encodings = None
  
  @property
  def option_encodings(self):
    '''
    A dictionary containing option_name:option_encoding pairs where option_name
    is how the option can be passed to the controller's __init__() and
    option_encoding is how the option value should be passed at the command line.
    
    Deriving classes should override class attribute _option_encodings with
    their dict of encodings in order to use this feature.
    
    Example:
        Encoding 'number':'-n=' will result in number=5 passed as argument to
        __init__() being encoded as '-n=5'
    
    Note:
        For options with a value, the separator between the option flag and the
        value ('=' in above example) must be included in the encoding, otherwise
        no separator will be inserted.
    '''
    return self._option_encodings
  
  @staticmethod
  def format_option_str(key,sep,val):
    '''
    Assumes standard long and short option prefix convention:
      * a one-letter option is prefixed with '-'
      * an option longer than one letter is prefixed with a '--'
    '''
    if key[0] != '-':
      prefix = '-' if len(key) == 1 else '--'
      key = prefix+key
    
    if val is True:
      formatted_option = key
    elif val is False:
      formatted_option = ''
    else:
      formatted_option = "%s%s%s" % (key,sep,val)
    return formatted_option
  
  def __init__(self,callargs=None,callkwargs=None,option_sep='='):
    # Modifying original callargs makes partials too messy, so make a copy
    self.callargs = [a for a in callargs] if callargs is not None else None
    self.callkwargs = callkwargs
    self.optionsep = option_sep
  
  def construct_call_string(self):
    # Get name of command to execute from class attribute or from callargs
    try:
      callstr_pieces = [self.command if self.command else self.callargs.pop(0)]
    except (TypeError,IndexError):
      raise ValueError("Name of command to be executed must be accessible via"\
                       " self.command (must not return empty string) or passed"\
                       " as first positional argument")
    
    if self.callkwargs:
      callkwargscopy = self.callkwargs.copy()
      processed_callkwargs = []
      for k in self.callkwargs:
        try:
          known_encoding = self.option_encodings.get(k)
        except AttributeError:
          break
        if known_encoding is not None:
          processed_callkwargs.append(self.format_option_str(known_encoding,'',
                                                        callkwargscopy.pop(k)))
      for k,v in callkwargscopy.items():
        processed_callkwargs.append(self.format_option_str(k,self.optionsep,v))
      callstr_pieces.extend(processed_callkwargs)
    
    if self.callargs:
      for a in self.callargs:
        callstr_pieces.append('%s' % a)
    
    self.callstr = ' '.join(callstr_pieces)
  
  def call(self):
    self.construct_call_string()
    CommandLineCaller.call(self,self.callstr)
