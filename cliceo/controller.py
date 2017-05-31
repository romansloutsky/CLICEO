import os
import subprocess
from . import contextmanagers


class CLIcontrollerBase(object):
  
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
  
  @classmethod
  def get_CLI_context_manager(cls):
    return contextmanagers.CLIcontextManager()
  
  def __init__(self,dirpath=None,in_tmpdir=False,PIDpublisher=None,silent=False,
               err_to_out=False,capture_stdout=False,capture_stderr=False,
               callargs=None,callkwargs=None,option_sep='='):
    self.dir = dirpath
    self.tmpdir = in_tmpdir
    self.PIDpublisher = PIDpublisher
    self.cliCM = self.get_CLI_context_manager()
    
    self.stdout = subprocess.PIPE if capture_stdout else False if silent\
                                                                      else None
    if err_to_out:
      self.stderr = subprocess.STDOUT
    else:
      self.stderr = subprocess.PIPE if capture_stderr else False if silent\
                                                                      else None
    
    # Get name of command to execute from class attribute or from callargs
    try:
      # Modifying original callargs makes partials too messy, so make a copy
      callargs = [a for a in callargs]
      callstr_pieces = [self.command if self.command else callargs.pop(0)]
    except (TypeError,IndexError):
      raise ValueError("Name of command to be executed must be accessible via"\
                       " self.command (must not return empty string) or passed"\
                       " as first positional argument")
    
    # Process callkwargs into call string pieces
    if callkwargs:
      callkwargscopy = callkwargs.copy()
      processed_callkwargs = []
      for k in callkwargs:
        try:
          known_encoding = self.option_encodings.get(k)
        except AttributeError:
          break
        if known_encoding is not None:
          processed_callkwargs.append(self.format_option_str(known_encoding,'',
                                                        callkwargscopy.pop(k)))
      for k,v in callkwargscopy.items():
        processed_callkwargs.append(self.format_option_str(k,option_sep,v))
      callstr_pieces.extend(processed_callkwargs)
    
    # Process callargs into call string pieces
    if callargs:
      for a in callargs:
        callstr_pieces.append('%s' % a)
    
    # Construct the call string
    self.callstr = ' '.join(callstr_pieces)
  
  def in_workdir(self,name):
    '''
    Path to arbitrary name placed in working directory
    '''
    return os.path.join(self.dir,name)
  
  def _run(self):
    child_p = subprocess.Popen(self.callstr,stdout=self.stdout,
                               stderr=self.stderr,shell=True)
    if callable(self.PIDpublisher):
      self.PIDpublisher(child_p.pid)
    child_p.communicate()
  
  def call(self):
    '''
    This method passes the call from __call__() to _run() running inside the
    CLI context.
    
    Deriving classes should extend this method with any activities that must
    be performed inside the CLI context before and/or after the call to _run()
    '''
    self._run()
  
  def __call__(self):
    if self.tmpdir:
      self.tmpdir = self.cliCM.enter_tmpdir(self.dir)
      self.dir = '.'
    
    if self.stdout is False or self.stderr is False:
      devnull = open(os.devnull,'w')
      self.cliCM.push(devnull)
      if self.stdout is False:
        self.stdout = devnull
      if self.stderr is False:
        self.stderr = devnull
    
    with self.cliCM:
      return self.call()
