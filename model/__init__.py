'''
Model Module
'''

from . import steg_net

# __xx：双下划线开头：私有变量
# ----只有该类能调用该变量，其子类或其他类均不能调用

# _xxx:单下划线开头：成员变量：
# ----只有通过实例化后才能进行调用，不能通过from module import ***导入
_models = [
    steg_net,
]

_dispatcher = {model.name(): model for model in _models}


def get_model_by_name(name):
  '''
  Helper function to obtain the model by its name
  '''
  if name == 'common':
    raise ImportError('common is reserved for utility use')
  return _dispatcher[name]
