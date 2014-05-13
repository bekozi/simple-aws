from ConfigParser import SafeConfigParser
import boto.ec2
import time


class AwsManager(object):
    """
    Configuration file structure:

    [:class:`AwsManager.section_title`]
    aws_access_key_id =
    aws_secret_access_key =
    image_id =
    instance_type =
    region =
    security_group =
    """

    def __init__(self, conf_path, filtered=True, only_running=True, section_title='aws'):
        self.conf_path = conf_path
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
        return(self._conn)

    def get_instances(self):
        reservations = self.conn.get_all_reservations()
        instances = [i for r in reservations for i in r.instances]
        instances = {i.id: i for i in instances}
        if self.only_running:
            instances = {i.id: i for i in instances.values() if i.update() == 'running'}
        if self.filtered:
            instances = {i.id: i for i in instances.values() if self._filter_(i)}
        return(instances)

    def get_instance_by_name(self, name):
        ret = None
        for instance in self.get_instances().itervalues():
            if instance.tags['Name'] == name:
                ret = instance
        if ret is None:
            raise(ValueError('Name not found.'))
        else:
            return(ret)

    def launch_new_instance(self, name, wait=True):
        image_id = self._cfg['image_id']
        security_group = self._cfg['security_group']
        instance_type = self._cfg['instance_type']
        key_name = self._cfg['key_name']

        if not self._get_is_unique_tag_(name, 'Name'):
            msg = 'The assigned instance name "{0}" is not unique.'.format(name)
            raise(ValueError(msg))

        reservation = self.conn.run_instances(image_id, key_name=key_name, instance_type=instance_type, security_groups=[security_group])
        instance = reservation.instances[0]
        self.conn.create_tags([instance.id], {"Name": name})

        if wait:
            status = instance.update()
            while status != 'running':
                time.sleep(1)
                status = instance.update()

        return(instance)

    def _filter_(self, instance):
        if instance.key_name == self._cfg['key_name']:
            ret = True
        else:
            ret = False
        return(ret)

    def _get_aws_connection_(self):
        region = self._cfg['region']

        aws_access_key_id = self._cfg['aws_access_key_id']
        aws_secret_access_key = self._cfg['aws_secret_access_key']

        conn = boto.ec2.connect_to_region(region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

        if conn is None:
            raise(RuntimeError('Unable to launch instance.'))

        return(conn)

    def _get_is_unique_tag_(self, tag_value, tag_key):
        instances = self.get_instances()
        ret = True
        for i in instances.itervalues():
            if i.tags.get(tag_key) == tag_value:
                ret = False
        return(ret)
