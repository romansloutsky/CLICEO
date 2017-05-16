import os
import tempfile
import contextlib2

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

