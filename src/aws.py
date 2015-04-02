from ConfigParser import SafeConfigParser
from email.mime.text import MIMEText
import os
from boto import ses
import boto.ec2
import time
from boto.ec2.address import Address
from exc import InstanceNameNotAvailable


class AwsManager(object):
    """
    :param str conf_path: Path to the configuration file. See *simple-aws.conf.TEMPLATE* for structure.
    :param bool filtered: If ``True``, only consider instances attached to ``key_name`` in the configuration file.
    :param bool only_running: If ``True``, only consider running instances.
    :param str section_title: The title of the section in the configuration file to read values from.
    """

    def __init__(self, conf_path=None, filtered=True, only_running=True, section_title='simple-aws'):
        if conf_path is None:
            msg = 'Path to configuration file required.'
            raise ValueError(msg)

        self.conf_path = conf_path or os.path.expanduser(os.getenv('SIMPLEAWS_CONF_PATH'))
        self.filtered = filtered
        self.only_running = only_running
        self._conn = None
        self._parser = SafeConfigParser()
        self._parser.read(self.conf_path)
        self._cfg = dict(self._parser.items(section_title))

    @property
    def conn(self):
        if self._conn is None:
            self._conn = self._get_aws_connection_()
        return self._conn

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

        reservations = self.conn.get_all_reservations()
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

    def launch_new_instance(self, name, image_id=None, instance_type=None, placement=None, elastic_ip=None, wait=True):
        image_id = image_id or self._cfg['image_id']
        instance_type = instance_type or self._cfg['instance_type']
        security_group = self._cfg['security_group']
        key_name = self._cfg['key_name']

        if not self._get_is_unique_tag_(name, 'Name'):
            msg = 'The assigned instance name "{0}" is not unique.'.format(name)
            raise ValueError(msg)

        reservation = self.conn.run_instances(image_id, key_name=key_name, instance_type=instance_type,
                                              security_groups=[security_group], placement=placement)
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

        aws_access_key_id = self._cfg['aws_access_key_id']
        aws_secret_access_key = self._cfg['aws_secret_access_key']
        conn = ses.connect_to_region(self._cfg['region'], aws_access_key_id=aws_access_key_id,
                                     aws_secret_access_key=aws_secret_access_key)
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
    def wait_for_status(target, status_target, sleep=1, pad=None):
        time.sleep(sleep)
        while target.update() != status_target:
            time.sleep(sleep)
        if pad is not None:
            time.sleep(pad)

    def _filter_(self, instance):
        if instance.key_name == self._cfg['key_name']:
            ret = True
        else:
            ret = False
        return ret

    def _get_aws_connection_(self):
        region = self._cfg['region']

        aws_access_key_id = self._cfg['aws_access_key_id']
        aws_secret_access_key = self._cfg['aws_secret_access_key']

        conn = boto.ec2.connect_to_region(region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

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
