from ConfigParser import SafeConfigParser
from email.mime.text import MIMEText
import os
import time

from boto import ses
import boto.ec2
from boto.ec2.address import Address
from boto.ec2.blockdevicemapping import BlockDeviceMapping, BlockDeviceType
from exc import InstanceNameNotAvailable
from saws.exc import RequiredVariableMissing

SIMPLEAWS_SECTION_TITLE = 'simple-aws'
SIMPLEAWS_ROOT_USER = 'ubuntu'


class AwsManager(object):
    """
    :param str conf_path: See :class:`saws.manager.AwsManagerConfiguration`.
    :param bool filtered: If ``True``, only consider instances attached to ``key_name`` in the configuration file.
    :param bool only_running: If ``True``, only consider running instances.
    :param str section_title: See :class:`saws.manager.AwsManagerConfiguration`.
    :param conf: Configuration object used in place of configuration file.
    :type conf: :class:`saws.manager.AwsManagerConfiguration`
    """

    def __init__(self, conf_path=None, filtered=True, only_running=True, section_title=SIMPLEAWS_SECTION_TITLE,
                 conf=None):
        if conf is None:
            conf = AwsManagerConfiguration(conf_path=conf_path, section_title=section_title)
        self.conf = conf
        self.filtered = filtered
        self.only_running = only_running
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = self._get_aws_connection_()
        return self._conn

    def do_task(self, taskf, name=None, instance=None, args=None, kwargs=None, user='ubuntu'):
        from fabric.context_managers import settings

        if name is None and instance is None:
            use_env = True
        else:
            use_env = False

        if not use_env and instance is None:
            instance = self.get_instance_by_name(name)

        args = args or []
        kwargs = kwargs or {}

        if use_env:
            taskf(*args, **kwargs)
        else:
            with settings(host_string=instance.ip_address, disable_known_hosts=True, connection_attempts=10,
                          user=user, key_filename=self.conf.aws_key_path):
                taskf(*args, **kwargs)

    def get_instances(self, key='id'):

        def _get_key_(instance):
            if key == 'id':
                ret = instance.id
            elif key == 'name':
                try:
                    ret = instance.tags['Name']
                except KeyError:
                    ret = instance.id
            else:
                raise NotImplementedError(key)
            return ret

        reservations = self.conn.get_all_instances()
        instances = [i for r in reservations for i in r.instances]
        instances = {i.id: i for i in instances}
        if self.only_running:
            instances = {_get_key_(i): i for i in instances.values() if i.update() == 'running'}
        if self.filtered:
            instances = {_get_key_(i): i for i in instances.values() if self._filter_(i)}
        return instances

    def get_instance_by_name(self, name):
        ret = None
        for instance in self.get_instances().itervalues():
            if instance.tags['Name'] == name:
                ret = instance
        if ret is None:
            raise InstanceNameNotAvailable('Name not found.')
        else:
            return ret

    def get_ssh_command(self, name=None, instance=None, root_user=SIMPLEAWS_ROOT_USER):
        if instance is None:
            instance = self.get_instance_by_name(name)
        root_user = root_user or self.conf.aws_root_user
        msg = 'ssh -i {0} {1}@{2}'.format(self.conf.aws_key_path, root_user, instance.ip_address)
        return msg

    def launch_new_instance(self, name, image_id=None, instance_type=None, placement=None, elastic_ip=None, wait=True,
                            ebs_snapshot_id=None, ebs_mount_name='/dev/xvdg'):
        image_id = image_id or self.conf.aws_image_id
        instance_type = instance_type or self.conf.aws_instance_type
        security_group = self.conf.aws_security_group
        key_name = self.conf.aws_key_name

        if not self._get_is_unique_tag_(name, 'Name'):
            msg = 'The assigned instance name "{0}" is not unique.'.format(name)
            raise ValueError(msg)

        block_device_map = None
        if ebs_snapshot_id is not None:
            block_device_map = BlockDeviceMapping()
            block_dev_type = BlockDeviceType()
            block_dev_type.delete_on_termination = True
            block_dev_type.snapshot_id = ebs_snapshot_id
            block_device_map[ebs_mount_name] = block_dev_type

        reservation = self.conn.run_instances(image_id, key_name=key_name, instance_type=instance_type,
                                              security_groups=[security_group], placement=placement,
                                              block_device_map=block_device_map)
        instance = reservation.instances[0]

        if wait:
            self.wait_for_status(instance, 'running')

        self.conn.create_tags([instance.id], {"Name": name})

        if elastic_ip:
            address = Address(connection=self.conn, public_ip=elastic_ip)
            address.associate(instance_id=instance.id)
            instance.update()

        return instance

    def send_email(self, fromaddr, recipient, subject, body):
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = fromaddr
        msg['To'] = recipient

        aws_access_key = self.conf.aws_access_key
        aws_secret_key = self.conf.aws_secret_key
        conn = ses.connect_to_region(self.conf.aws_region, aws_access_key_id=aws_access_key,
                                     aws_secret_access_key=aws_secret_key)
        conn.send_raw_email(msg.as_string())

    def start_instance_by_name(self, name, wait=True):
        prev_only_running = self.only_running
        self.only_running = False
        try:
            instance = self.get_instance_by_name(name)
            status = instance.update()
            status_target = 'running'
            if status != status_target:
                instance.start()
                if wait:
                    self.wait_for_status(instance, status_target)
            return instance
        finally:
            self.only_running = prev_only_running

    @staticmethod
    def wait_for_status(instance, status_target, sleep=1, pad=3):
        time.sleep(sleep)
        while instance.update() != status_target:
            time.sleep(sleep)
        if pad is not None:
            time.sleep(pad)

    def _filter_(self, instance):
        if instance.key_name == self.conf.aws_key_name:
            ret = True
        else:
            ret = False
        return ret

    def _get_aws_connection_(self):
        conn = boto.ec2.connect_to_region(self.conf.aws_region, aws_access_key_id=self.conf.aws_access_key,
                                          aws_secret_access_key=self.conf.aws_secret_key)
        if conn is None:
            raise RuntimeError('Unable to launch instance.')
        return conn

    def _get_is_unique_tag_(self, tag_value, tag_key):
        instances = self.get_instances()
        ret = True
        for i in instances.itervalues():
            if i.tags.get(tag_key) == tag_value:
                ret = False
        return ret


class AwsManagerConfiguration(object):
    """
    :class:`saws.AwsManager` configuration object. Any of the keywords arguments found in
    :attr:`saws.AwsManagerConfiguration._kwargs` may be set in the following ways (in order of precedence):
     * Passed as keyword arguments to the constructor.
     * Set as uppercase environment variables.
     * Set in the configuration file.

    :keyword str conf_path: (``=None``) Path to the configuration file. The environment variable
     ``'SIMPLEAWS_CONF_PATH'`` may also be used.
    :keyword str section_title: (``='simple-aws'``) Name of the section in the configuration file to look for values.
    :keyword kwargs: Any keyword from :attr:`saws.AwsManagerConfiguration._kwargs`.
    :raises: ValueError
    """

    _kwargs = {'aws_access_key': False, 'aws_secret_key': False, 'aws_image_id': True, 'aws_instance_type': True,
               'aws_region': False, 'aws_security_group': True, 'aws_key_name': True, 'aws_key_path': False,
               'aws_root_user': True}

    def __init__(self, **kwargs):
        self.conf_path = kwargs.pop('conf_path', None)
        if self.conf_path is None:
            self.conf_path = os.environ.get('SIMPLEAWS_CONF_PATH')
        self.section_title = kwargs.pop('section_title', SIMPLEAWS_SECTION_TITLE)

        cfg_kwargs = {}
        for kwarg in self._kwargs.iterkeys():
            value = kwargs.get(kwarg)
            if value is None:
                value = os.environ.get(kwarg)
                if value is None:
                    value = os.environ.get(kwarg.upper())
            cfg_kwargs[kwarg] = value

        cfg_conf = {}
        if self.conf_path is not None:
            self.conf_path = os.path.expanduser(self.conf_path)
            parser = SafeConfigParser()
            parser.read(self.conf_path)
            cfg_conf = dict(parser.items(self.section_title))

        for k, v in cfg_conf.iteritems():
            if cfg_kwargs.get(k) is None:
                cfg_kwargs[k] = v

        for k, v in cfg_kwargs.iteritems():
            if v is None and not self._kwargs[k]:
                msg = 'The configuration key "{0}" may not be None.'.format(k)
                raise RequiredVariableMissing(msg)
            else:
                setattr(self, k, v)
