import os
import unittest
from mock import patch,mock_open,Mock
import subprocess
from tempfile import template as TEMPFILE_TEMPLATE
from cliceo import controller

@patch('subprocess.Popen')
class test_CommandLineCaller(unittest.TestCase):
  
  def test_subprocess_creation_and_CL_call(self,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycontroller = controller.CommandLineCaller('dummy_callstr')
    dummycontroller()
    patched_Popen.assert_called_once_with('dummy_callstr',
                                          stdout=dummycontroller.stdout,
                                          stderr=dummycontroller.stderr,
                                          shell=True)
    patched_Popen.return_value.communicate.assert_called_once_with()
  
  def test_PID_reporting(self,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    mockPIDpublisher = Mock()
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   PIDpublisher=mockPIDpublisher)
    dummycontroller()
    mockPIDpublisher.assert_called_once_with(patched_Popen.return_value.pid)
  
  @patch('cliceo.tempdir.TemporaryWorkingDirectory')
  def test_in_tmpdir_default_OS_loc(self,patched_TWD,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   in_tmpdir=True)
    dummycontroller()
    # This is how TemporaryWorkingDirectory is called by CLIcontextManager,
    # which manages the temporary directory context for CommandLineCaller
    patched_TWD.assert_called_once_with(dir=None,prefix=TEMPFILE_TEMPLATE,
                                        suffix='')
  
  @patch('cliceo.tempdir.TemporaryWorkingDirectory')
  def test_in_tmpdir_at_specified_loc(self,patched_TWD,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   in_tmpdir=True,
                                                   tmpdir_loc='/desired/loc')
    dummycontroller()
    patched_TWD.assert_called_once_with(dir='/desired/loc',
                                        prefix=TEMPFILE_TEMPLATE,suffix='')
  
  @patch('cliceo.tempdir.TemporaryWorkingDirectory')
  def test_in_tmpdir_precedence_over_tmpdir_loc(self,patched_TWD,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   tmpdir_loc='/desired/loc')
    self.assertFalse(patched_TWD.called)
  
  def test_stdout_capture(self,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   capture_stdout=True)
    dummycontroller()
    patched_Popen.assert_called_once_with('dummy_callstr',
                                          stdout=subprocess.PIPE,stderr=None,
                                          shell=True)
    self.assertEqual(dummycontroller.captured_stdout,'dummySTDOUT')
  
  @patch('__builtin__.open',new_callable=mock_open)
  def test_stdout_silencing(self,patched_open,patched_Popen):
    patched_Popen.return_value.communicate.return_value = (None,None)
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   silence_stdout=True)
    dummycontroller()
    self.assertIs(dummycontroller.captured_stdout,None)
    patched_open.assert_called_once_with(os.devnull,'w')
    patched_Popen.assert_called_once_with('dummy_callstr',
                                          stdout=patched_open.return_value,
                                          stderr=None,shell=True)
  
  @patch('__builtin__.open',new_callable=mock_open)
  def test_stdout_capture_precedence_over_silence(self,patched_open,
                                                       patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   capture_stdout=True,
                                                   silence_stdout=True)
    dummycontroller()
    self.assertEqual(dummycontroller.captured_stdout,'dummySTDOUT')
    self.assertFalse(patched_open.called)
  
  def test_stderr_capture(self,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   capture_stderr=True)
    dummycontroller()
    patched_Popen.assert_called_once_with('dummy_callstr',
                                          stdout=None,stderr=subprocess.PIPE,
                                          shell=True)
    self.assertEqual(dummycontroller.captured_stderr,'dummySTDERR')
  
  @patch('__builtin__.open',new_callable=mock_open)
  def test_stderr_silencing(self,patched_open,patched_Popen):
    patched_Popen.return_value.communicate.return_value = (None,None)
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   silence_stderr=True)
    dummycontroller()
    self.assertIs(dummycontroller.captured_stderr,None)
    patched_open.assert_called_once_with(os.devnull,'w')
    patched_Popen.assert_called_once_with('dummy_callstr',stdout=None,
                                          stderr=patched_open.return_value,
                                          shell=True)
  
  @patch('__builtin__.open',new_callable=mock_open)
  def test_stderr_capture_precedence_over_silence(self,patched_open,
                                                       patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   capture_stderr=True,
                                                   silence_stderr=True)
    dummycontroller()
    self.assertEqual(dummycontroller.captured_stderr,'dummySTDERR')
    self.assertFalse(patched_open.called)
  
  def test_stderr_redirection_to_stdout(self,patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   err_to_out=True)
    self.assertIs(dummycontroller.stderr,subprocess.STDOUT)
    dummycontroller()
    patched_Popen.assert_called_once_with('dummy_callstr',stdout=None,
                                          stderr=subprocess.STDOUT,shell=True)
    
  
  @patch('__builtin__.open',new_callable=mock_open)
  def test_stderr_redirection_to_stdout_precedence(self,patched_open,
                                                        patched_Popen):
    patched_Popen.return_value.communicate.return_value = ('dummySTDOUT',
                                                           'dummySTDERR')
    dummycontroller = controller.CommandLineCaller('dummy_callstr',
                                                   err_to_out=True,
                                                   capture_stderr=True,
                                                   silence_stderr=True)
    self.assertIs(dummycontroller.stderr,subprocess.STDOUT)
    dummycontroller()
    self.assertFalse(patched_open.called)

# @patch('subprocess.Popen')
# class test_CLIcontrollerBase_std_stream_handling(unittest.TestCase):
#   
#   def test_std_stream_capture(self,patched_Popen):
#     patched_Popen.return_value.communicate.return_value = (None,None)
#     dummycontroller = controller.CLIcontrollerBase(capture_stdout=True,
#                                                    callargs=['ls'])
#     self.assertIs(dummycontroller.stdout,subprocess.PIPE)
#     self.assertIs(dummycontroller.stderr,None)
#     dummycontroller()
#     patched_Popen.assert_called_once_with('ls',stdout=subprocess.PIPE,
#                                           stderr=None,shell=True)
#     dummycontroller = controller.CLIcontrollerBase(capture_stderr=True,
#                                                    callargs=['ls'])
#     self.assertIs(dummycontroller.stdout,None)
#     self.assertIs(dummycontroller.stderr,subprocess.PIPE)
#     dummycontroller()
#     patched_Popen.assert_called_with('ls',stdout=None,
#                                      stderr=subprocess.PIPE,shell=True)
#     
#   def test_stderr_to_stdout(self,patched_Popen):
#     patched_Popen.return_value.communicate.return_value = (None,None)
#     dummycontroller = controller.CLIcontrollerBase(err_to_out=True,
#                                                    callargs=['ls'])
#     self.assertIs(dummycontroller.stderr,subprocess.STDOUT)
#     dummycontroller()
#     patched_Popen.assert_called_with('ls',stderr=subprocess.STDOUT,
#                                      stdout=None,shell=True)
#   
#   @patch('__builtin__.open',new_callable=mock_open)
#   def test_std_stream_redirection_to_null(self,mockopen,patched_Popen):
#     patched_Popen.return_value.communicate.return_value = (None,None)
#     mockfh = mockopen.return_value
#     
#     dummycontroller = controller.CLIcontrollerBase(silent=True,callargs=['ls'])
#     self.assertItemsEqual(mockopen.call_args_list,[])
#     dummycontroller()
#     mockopen.assert_called_once_with(os.devnull,'w')
#     patched_Popen.assert_called_once_with('ls',stdout=mockfh,stderr=mockfh,
#                                           shell=True)
#     mockfh.__exit__.assert_called_once_with(mockfh,None,None,None)
#     
#     mockfh.reset_mock()
#     dummycontroller = controller.CLIcontrollerBase(silent=True,
#                                                    capture_stdout=True,
#                                                    callargs=['ls'])
#     dummycontroller()
#     mockopen.assert_called_with(os.devnull,'w')
#     patched_Popen.assert_called_with('ls',stdout=subprocess.PIPE,stderr=mockfh,
#                                      shell=True)
#     mockfh.__exit__.assert_called_once_with(mockfh,None,None,None)
# 
# 
# class test_CLIcontrollerBase_working_directory(unittest.TestCase):
#   
#   def test_regular_working_directory(self):
#     dummycontroller = controller.CLIcontrollerBase(callargs=['ls'])
#     self.assertEqual(dummycontroller.in_workdir('dummy'),
#                      os.path.join('.','dummy'))
#     
#     dummycontroller = controller.CLIcontrollerBase(dirpath='different_dir',
#                                                    callargs=['ls'])
#     self.assertEqual(dummycontroller.in_workdir('dummy'),
#                      os.path.join('different_dir','dummy'))
#   
#   @patch('subprocess.Popen')
#   @patch('cliceo.tempdir.TemporaryWorkingDirectory')
#   def test_temporary_working_directory(self,patched_TmpWorkDir,patched_Popen):
#     patched_Popen.return_value.communicate.return_value = (None,None)
#     mockTmpWorkDir_obj = patched_TmpWorkDir.return_value 
#     mockTmpWorkDir_obj.__enter__.return_value = 'created_temporary_dir'
#     dummycontroller = controller.CLIcontrollerBase(dirpath='different_dir',
#                                                    in_tmpdir=True,
#                                                    callargs=['ls'])
#     self.assertIs(dummycontroller.tmpdir,True)
#     self.assertEqual(dummycontroller.dir,'different_dir')
#     dummycontroller()
#     patched_TmpWorkDir.assert_called_once_with(dir='different_dir',
#                                                prefix='tmp',suffix='')
#     mockTmpWorkDir_obj.__enter__.assert_called_once_with(mockTmpWorkDir_obj)
#     self.assertIs(dummycontroller.tmpdir,
#                   mockTmpWorkDir_obj.__enter__.return_value)
#     self.assertEqual(dummycontroller.dir,'.')
#     self.assertEqual(dummycontroller.tmpdir,'created_temporary_dir')
#     self.assertEqual(dummycontroller.in_workdir('dummy'),
#                      os.path.join('.','dummy'))
#     mockTmpWorkDir_obj.__exit__.assert_called_once_with(mockTmpWorkDir_obj,
#                                                         None,None,None)
# 
# 
# class test_CLIcontrollerBase_calling(unittest.TestCase):
#   @patch('cliceo.contextmanagers.CLIcontextManager')
#   def test_call_happens_in_cliCM_context(self,patched_cliCM):
#     mock_cliCM_obj = patched_cliCM.return_value
#     
#     class DummyController(controller.CLIcontrollerBase):
#       def call(_self):
#         mock_cliCM_obj.__enter__.assert_called_once_with()
#         self.assertItemsEqual(mock_cliCM_obj.__exit__.call_args_list,[])
#     
#     
#     dummycontroller = DummyController(callargs=['ls'])
#     patched_cliCM.assert_called_once_with()
#     self.assertItemsEqual(mock_cliCM_obj.__enter__.call_args_list,[])
#     self.assertItemsEqual(mock_cliCM_obj.__exit__.call_args_list,[])
#     dummycontroller()
#     mock_cliCM_obj.__exit__.assert_called_once_with(None,None,None)
#   
#   @patch('subprocess.Popen')
#   def test_call_arg_and_kwarg_reusability(self,patched_Popen):
#     patched_Popen.return_value.communicate.return_value = (None,None)
#     dummypartial = controller.CLIcontrollerBase.partial(callargs=['ls'],
#                                                         callkwargs={'l':True})
#     dummypartial()
#     patched_Popen.assert_called_once_with('ls -l',stdout=None,stderr=None,
#                                           shell=True)
#     patched_Popen.reset_mock()
#     dummypartial()
#     patched_Popen.assert_called_once_with('ls -l',stdout=None,stderr=None,
#                                           shell=True)
#   
#   def test_base_call_string_formatting(self):
#     dummycontroller = controller.CLIcontrollerBase(callargs=['ls','d1','d2'],
#                                                    callkwargs={'l':True,
#                                                                '-a':True,
#                                                                'false':False,
#                                                                'u':'unknown',
#                                                                'another':'a'},
#                                                    option_sep='->')
#     dummycontroller.construct_call_string()
#     self.assertEqual(dummycontroller.callstr.split()[0],'ls')
#     self.assertItemsEqual(dummycontroller.callstr.split()[1:],
#                           ['-l','-a','-u->unknown','--another->a','d1','d2'])
#   
#   def test_command_and_option_encoding_in_child_controller_class(self):
#     class DummyController(controller.CLIcontrollerBase):
#       _command = 'ls'
#       _option_encodings = {'longform':'-l','valueoption':'-vo='}
#     
#     dummycontroller = DummyController(callkwargs={'longform':True,
#                                                   'valueoption':'value',
#                                                   'u':'unknown','another':'a'},
#                                       option_sep='->')
#     dummycontroller.construct_call_string()
#     self.assertEqual(dummycontroller.callstr.split()[0],'ls')
#     self.assertItemsEqual(dummycontroller.callstr.split()[1:],
#                           ['-l','-vo=value','-u->unknown','--another->a'])
