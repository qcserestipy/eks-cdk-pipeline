class Account:

    @property
    def label(self):
        return self._account_label
    
    @property
    def id(self):
        return self._account_id
    
    @property
    def region(self):
        return self._account_region
    
    @staticmethod
    def account_id_from_label(account_label, config):
        try:
            return config["accounts"][account_label]["id"]
        except:
            return None

    @staticmethod
    def account_label_from_id(account_id, config):
        try:
            for k, v in config["accounts"].items():
                if v["id"] == account_id:
                    return k
        except:
            return None

    def __init__(self, account_label, config, account_region=None):
        self._account_label = account_label
        self._account_id = config["accounts"][account_label]["id"]
        if account_region is None:
            account_region = config["pipeline"]["account"]["region"]
        self._account_region = account_region
