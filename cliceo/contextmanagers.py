import os
import tempfile
import contextlib2
from . import tempdir


@contextlib2.contextmanager
def NamedTemporaryFileWithContents(contents,dirpath=None,bufsize=-1,mode='w+b',
                                   suffix="",prefix=tempfile.template):
  '''
  Temporary file holding contents expected to be found in a file by a third
  party, e.g. a CLI application.
  
  Argument contents may be a string to be written to the file or a callable that
  takes a single argument, the file handle, and does the writing itself.
  '''
  try:
    with tempfile.NamedTemporaryFile(mode=mode,bufsize=bufsize,suffix=suffix,
                                     prefix=prefix,dir=dirpath,delete=False)\
                                                               as tempfile_obj:
      if callable(contents):
        contents(tempfile_obj.file)
      else:
        tempfile_obj.file.write(contents)
    yield tempfile_obj.name
  finally:
    tempfile_obj.unlink(tempfile_obj.name)


@contextlib2.contextmanager
def RemoveFileOnExit(fpath):
  unlink = os.unlink
  try:
    yield fpath
  finally:
    unlink(fpath)


class CLIcontextManager(object):
  def __enter__(self):
    return self
    
  @property
  def exitstack(self):
    if not hasattr(self,'_exitstack'):
      self._exitstack = contextlib2.ExitStack()
    return self._exitstack
  
  def push(self,cm):
    return self.exitstack.push(cm)
  
  def enter_tmpdir(self,dirpath=None,suffix="",prefix=tempfile.template):
    return self.exitstack.enter_context(tempdir.TemporaryWorkingDirectory(
                                                                 suffix=suffix,
                                                                 prefix=prefix,
                                                                 dir=dirpath))
  
  def write_to_tempfile(self,contents,dirpath=None,bufsize=-1,mode='w+b',
                        suffix="",prefix=tempfile.template):
    return self.exitstack.enter_context(NamedTemporaryFileWithContents(
                                                             contents=contents,
                                                             dirpath=dirpath,
                                                             bufsize=bufsize,
                                                             mode=mode,
                                                             suffix=suffix,
                                                             prefix=prefix))
  
  def register_for_removal(self,fpath):
    self.push(RemoveFileOnExit(fpath))
  
  def random_name(self,dirpath=None,suffix="",prefix=tempfile.template):
    dirpath = '.' if dirpath is None else dirpath
    names_generator = tempfile._get_candidate_names()
    name_candidate = prefix+names_generator.next()+suffix
    while os.path.exists(os.path.join(dirpath,name_candidate)):
      name_candidate = prefix+names_generator.next()+suffix
    return name_candidate if dirpath == '.'\
                                      else os.path.join(dirpath,name_candidate)
  
  def __exit__(self,*exception_details):
    if hasattr(self,'_exitstack'):
      self._exitstack.close()
