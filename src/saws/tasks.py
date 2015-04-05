from fabric.decorators import task
from fabric.operations import run, sudo
import time


@task
def ebs_mount(mount_name='/dev/xvdg', mount_dir='~/data', sleep=5):
    run('mkdir -p {0}'.format(mount_dir))
    time.sleep(sleep)
    cmd = ['mount', mount_name, mount_dir]
    sudo(' '.join(cmd))
