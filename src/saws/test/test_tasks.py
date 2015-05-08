import os
from tempfile import mkstemp
from fabric.context_managers import cd
from saws import AwsManager
from saws.tasks import run_bash_script
from saws.test.test_saws import AbstractTestSimpleAws, CONF_PATH


class TestTasks(AbstractTestSimpleAws):

    def test_run_bash_script(self):

        def _exists_():
            with cd('~/a-new-directory'):
                self.assertTrue(True)

        _, script = mkstemp()
        try:
            with open(script, 'w') as f:
                f.write('mkdir ~/a-new-directory\n')
            m = AwsManager(CONF_PATH)
            assert self.shared_instance
            m.do_task(run_bash_script, name=self.shared_instance_name, args=(script,))
            m.do_task(_exists_, name=self.shared_instance_name)
        finally:
            os.remove(script)