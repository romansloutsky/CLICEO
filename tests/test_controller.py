import os
import unittest
from mock import patch,mock_open
import subprocess
from procCEO import controller


@patch('subprocess.Popen')
class test_CLIcontrollerBase_std_stream_handling(unittest.TestCase):
  
  def test_std_stream_capture(self,patched_Popen):
    dummycontroller = controller.CLIcontrollerBase(capture_stdout=True,
                                                   callargs=['ls'])
    self.assertIs(dummycontroller.stdout,subprocess.PIPE)
    self.assertIs(dummycontroller.stderr,None)
    dummycontroller()
    patched_Popen.assert_called_once_with('ls',stdout=subprocess.PIPE,
                                          stderr=None,shell=True)
    dummycontroller = controller.CLIcontrollerBase(capture_stderr=True,
                                                   callargs=['ls'])
    self.assertIs(dummycontroller.stdout,None)
    self.assertIs(dummycontroller.stderr,subprocess.PIPE)
    dummycontroller()
    patched_Popen.assert_called_with('ls',stdout=None,
                                     stderr=subprocess.PIPE,shell=True)
    
  def test_stderr_to_stdout(self,patched_Popen):
    dummycontroller = controller.CLIcontrollerBase(err_to_out=True,
                                                   callargs=['ls'])
    self.assertIs(dummycontroller.stderr,subprocess.STDOUT)
    dummycontroller()
    patched_Popen.assert_called_with('ls',stderr=subprocess.STDOUT,
                                     stdout=None,shell=True)
  
  @patch('__builtin__.open',new_callable=mock_open)
  def test_std_stream_redirection_to_null(self,mockopen,patched_Popen):
    mockfh = mockopen.return_value
    
    dummycontroller = controller.CLIcontrollerBase(silent=True,callargs=['ls'])
    self.assertItemsEqual(mockopen.call_args_list,[])
    dummycontroller()
    mockopen.assert_called_once_with(os.devnull,'w')
    patched_Popen.assert_called_once_with('ls',stdout=mockfh,stderr=mockfh,
                                          shell=True)
    mockfh.__exit__.assert_called_once_with(mockfh,None,None,None)
    
    mockfh.reset_mock()
    dummycontroller = controller.CLIcontrollerBase(silent=True,
                                                   capture_stdout=True,
                                                   callargs=['ls'])
    dummycontroller()
    mockopen.assert_called_with(os.devnull,'w')
    patched_Popen.assert_called_with('ls',stdout=subprocess.PIPE,stderr=mockfh,
                                     shell=True)
    mockfh.__exit__.assert_called_once_with(mockfh,None,None,None)


class test_CLIcontrollerBase_working_directory(unittest.TestCase):
  
  def test_regular_working_directory(self):
    dummycontroller = controller.CLIcontrollerBase(callargs=['ls'])
    self.assertEqual(dummycontroller.in_workdir('dummy'),
                     os.path.join('.','dummy'))
    
    dummycontroller = controller.CLIcontrollerBase(dirpath='different_dir',
                                                   callargs=['ls'])
    self.assertEqual(dummycontroller.in_workdir('dummy'),
                     os.path.join('different_dir','dummy'))
  
  @patch('subprocess.Popen')
  @patch('procCEO.tempdir.TemporaryWorkingDirectory')
  def test_temporary_working_directory(self,patched_TmpWorkDir,patched_Popen):
    mockTmpWorkDir_obj = patched_TmpWorkDir.return_value 
    mockTmpWorkDir_obj.__enter__.return_value = 'created_temporary_dir'
    dummycontroller = controller.CLIcontrollerBase(dirpath='different_dir',
                                                   in_tmpdir=True,
                                                   callargs=['ls'])
    self.assertIs(dummycontroller.tmpdir,True)
    self.assertEqual(dummycontroller.dir,'different_dir')
    dummycontroller()
    patched_TmpWorkDir.assert_called_once_with(dir='different_dir',
                                               prefix='tmp',suffix='')
    mockTmpWorkDir_obj.__enter__.assert_called_once_with(mockTmpWorkDir_obj)
    self.assertIs(dummycontroller.tmpdir,
                  mockTmpWorkDir_obj.__enter__.return_value)
    self.assertEqual(dummycontroller.dir,'.')
    self.assertEqual(dummycontroller.in_workdir('dummy'),
                     os.path.join('.','dummy'))
    mockTmpWorkDir_obj.__exit__.assert_called_once_with(mockTmpWorkDir_obj,
                                                        None,None,None)


