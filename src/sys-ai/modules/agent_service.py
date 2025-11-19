import servicemanager
import win32serviceutil
import win32service
import win32event
import sys
import os
from agent_worker import AgentWorker

SERVICE_NAME = "sysai_agent"
SERVICE_DISPLAY_NAME = "SYS-AI Monitoring Agent"
SERVICE_DESC = "Background agent for SYS-AI - collects system metrics and executes admin commands."

class SysAIService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESC

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        # Create an event which we will use to wait on.
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.worker = AgentWorker()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.worker.stop()
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        try:
            self.worker.run()
        except Exception as e:
            servicemanager.LogErrorMsg(f"SysAIService exception: {e}")
            raise

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Called by the service manager
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SysAIService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # command line: install/remove/start/stop
        win32serviceutil.HandleCommandLine(SysAIService)
