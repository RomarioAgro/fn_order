import configparser

class ConfigLoader:
    def __init__(self, config_path="config.ini"):
        self.config = configparser.ConfigParser(interpolation=None)
        self.config.read(config_path)

    def get(self, section, key, as_type=str):
        value = self.config.get(section, key)
        if as_type == bool:
            return self.config.getboolean(section, key)
        elif as_type == int:
            return self.config.getint(section, key)
        elif as_type == float:
            return self.config.getfloat(section, key)
        return value  # как строка по умолчанию