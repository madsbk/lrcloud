import sys
if sys.version_info >= (3,):
    import configparser as cparser
else:
    import ConfigParser as cparser
import logging
from os.path import join, basename, dirname, isfile, abspath

def read(args):
    """Reading the configure file and adds non-existing attributes to 'args'"""

    if args.config_file is None or not isfile(args.config_file):
        return

    logging.info("Reading configure file: %s"%args.config_file)

    config = cparser.ConfigParser()
    config.read(args.config_file)
    if not config.has_section('lrcloud'):
        raise RuntimeError("Configure file has no [lrcloud] section!")

    for (name, value) in config.items('lrcloud'):
        if value == "True":
            value = True
        elif value == "False":
            value = False
        if getattr(args, name) is None:
            setattr(args, name, value)


def write(args):
    """Writing the configure file with the attributes in 'args'"""

    logging.info("Writing configure file: %s"%args.config_file)
    if args.config_file is None:
        return

    #Let's add each attribute of 'args' to the configure file
    config = cparser.ConfigParser()
    config.add_section("lrcloud")
    for p in [x for x in dir(args) if not x.startswith("_")]:
        if p in ['init_push_to_cloud', 'init_pull_from_cloud', \
                 'verbose', 'config_file', 'error']:
            continue#We ignore some attributes
        value = getattr(args, p)
        if value is not None:
            config.set('lrcloud', p, str(value))

    with open(args.config_file, 'w') as f:
        config.write(f)
