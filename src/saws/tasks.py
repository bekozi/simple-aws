from fabric.decorators import task
from fabric.operations import run, sudo, put
import time


@task
def ebs_mount(mount_name='/dev/xvdg', mount_dir='~/data', sleep=5):
    run('mkdir -p {0}'.format(mount_dir))
    time.sleep(sleep)
    cmd = ['mount', mount_name, mount_dir]
    sudo(' '.join(cmd))

@task
def run_bash_script(local_path, remote_path=None):
    if remote_path is None:
        remote_path = run('mktemp')
    put(local_path=local_path, remote_path=remote_path)
    try:
        run('bash {0}'.format(remote_path))
    finally:
        run('rm {0}'.format(remote_path))
