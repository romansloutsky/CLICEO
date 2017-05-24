import unittest
from mock import patch,Mock,MagicMock
from procCEO import contextmanagers


class test_NamedTemporaryFileWithContents(unittest.TestCase):
  
  @patch('tempfile.NamedTemporaryFile')
  def test_tempfile_creation_writing_and_unlinking(self,patched_cm_factory):
    patched_cm = patched_cm_factory.return_value.__enter__.return_value
    with contextmanagers.NamedTemporaryFileWithContents('dummy_contents',
                                                        dirpath='dummy_dir',
                                                suffix='dummy_suffix') as tmpf:
      patched_cm_factory.assert_called_once_with(dir='dummy_dir',bufsize=-1,
                                             mode='w+b',suffix='dummy_suffix',
                                             prefix='tmp',delete=False)
      self.assertIs(patched_cm.name,tmpf)
      patched_cm.file.write.assert_called_once_with('dummy_contents')
      self.assertItemsEqual(patched_cm.unlink.call_args_list,[])
    patched_cm.unlink.assert_called_once_with(patched_cm.name)
  
  @patch('tempfile.NamedTemporaryFile')
  def test_tempfile_writing_with_custom_writer(self,patched_cm_factory):
    patched_cm = patched_cm_factory.return_value.__enter__.return_value
    custom_writer = Mock()
    with contextmanagers.NamedTemporaryFileWithContents(custom_writer):
      custom_writer.assert_called_once_with(patched_cm.file)


class test_CLIcontextManager(unittest.TestCase):
  
  def setUp(self):
    self.cliCM = contextmanagers.CLIcontextManager()
  
  def test_handling_pushed_context(self):
    context_obj = MagicMock()
    self.cliCM.push(context_obj)
    with self.cliCM:
      self.assertItemsEqual(context_obj.__exit__.call_args_list,[])
    context_obj.__exit__.assert_called_once_with(context_obj,None,None,None)
  
  @patch('procCEO.tempdir.TemporaryWorkingDirectory')
  def test_handling_entered_tmpdir(self,
                                   patched_TemporaryWorkingDirectory_factory):
    patched_tmpdir_obj = patched_TemporaryWorkingDirectory_factory.return_value
    tmpdir = self.cliCM.enter_tmpdir()
    self.assertIs(tmpdir,patched_tmpdir_obj.__enter__.return_value)
    patched_TemporaryWorkingDirectory_factory.assert_called_once_with(dir=None,
                                                                     suffix="",
                                                                  prefix='tmp')
    patched_tmpdir_obj.__enter__.assert_called_once_with(patched_tmpdir_obj)
    with self.cliCM:
      self.assertItemsEqual(patched_tmpdir_obj.__exit__.call_args_list,[])
    patched_tmpdir_obj.__exit__.assert_called_once_with(patched_tmpdir_obj,
                                                        None,None,None)
  
  @patch('procCEO.contextmanagers.NamedTemporaryFileWithContents')
  def test_handling_written_tempfile(self,
                                     patched_NamedTemporaryFileWithContents):
    patched_tmpfile_obj = patched_NamedTemporaryFileWithContents.return_value
    tmpfpath = self.cliCM.write_to_tempfile('dummy_contents')
    self.assertIs(tmpfpath,patched_tmpfile_obj.__enter__.return_value)
    patched_NamedTemporaryFileWithContents.assert_called_once_with(mode='w+b',
                                                     contents='dummy_contents',
                                                     dirpath=None,bufsize=-1,
                                                     suffix="",prefix='tmp')
    patched_tmpfile_obj.__enter__.assert_called_once_with(patched_tmpfile_obj)
    with self.cliCM:
      self.assertItemsEqual(patched_tmpfile_obj.__exit__.call_args_list,[])
    patched_tmpfile_obj.__exit__.assert_called_once_with(patched_tmpfile_obj,
                                                        None,None,None)
    
  @patch('procCEO.contextmanagers.RemoveFileOnExit')
  def test_registering_for_removal(self,patched_RemoveFileOnExit):
    file_removing_obj = patched_RemoveFileOnExit.return_value
    self.cliCM.register_for_removal('dummy_filepath')
    patched_RemoveFileOnExit.assert_called_once_with('dummy_filepath')
    with self.cliCM:
      self.assertItemsEqual(file_removing_obj.__exit__.call_args_list,[])
    file_removing_obj.__exit__.assert_called_once_with(file_removing_obj,
                                                       None,None,None)
