'''
Steganography Model
'''

# pylint: disable=C0326, E1129, E0611
# 啊啊啊啊怎么是用tensorflow框架 die了
import tensorflow as tf
import tensorflow.contrib.slim as ts

import params
import ops
import tf_utils

# yapf: disable
fc            = ts.add_arg_scope(tf.layers.dense) # 全连接层
conv1d        = ts.add_arg_scope(tf.layers.conv1d) 
conv2d        = ts.add_arg_scope(tf.layers.conv2d) # 二维卷积层
sep_conv2d    = ts.add_arg_scope(tf.layers.separable_conv2d) # 转置卷积
max_pooling2d = ts.add_arg_scope(tf.layers.max_pooling2d) # 最大池化层
batch_norm    = ts.add_arg_scope(tf.layers.batch_normalization)
# yapf: enable

conv2d_activation = tf.nn.elu # 激活函数

# conv2d的参数值
conv2d_params = {
    'kernel_size': 3,
    'strides': (1, 1),
    'padding': 'SAME',
    'kernel_initializer': ts.xavier_initializer(),# 重置卷积核初始化权重参数
    'use_bias': True,  # 使用偏置值，但置为0
    'bias_initializer': tf.zeros_initializer(),
}

# 转置卷积么
sep_conv2d_params = {
    'kernel_size': 3,
    'strides': (1, 1),
    'dilation_rate': (1, 1),# 使用了dilation
    'depth_multiplier': 1,
    'padding': 'SAME',
    'depthwise_initializer': ts.xavier_initializer(),
    'pointwise_initializer': ts.xavier_initializer(),
    'use_bias': True,
    'bias_initializer': tf.zeros_initializer(),
}

batch_norm_params = {
    'momentum': 0.9,
    'epsilon': 1e-5,
    'center': True,
    'scale': True,
    'fused': False,
}


def skip_align(inputs, filters, strides, data_format):
  '''
  Pads the input along the channel dimension
  Args:
    inputs: A tensor NHWC or NCHW
    filters: num of filters for padded output  # 卷积核个数
    strides: the stride of the convolution operation
    data_format: 'channels_last' or 'channels_first'
  '''
  cnl_idx = 1 if data_format == 'channels_first' else 3
  paddings = [[0, 0], [0, 0], [0, 0], [0, 0]]

  inputs = tf.layers.average_pooling2d(inputs, 1, strides, padding='SAME', data_format=data_format) # 先放入一个平均池化层
  
  # 人工计算填充大小，并进行填充
  pad_total = filters - inputs.shape.as_list()[cnl_idx] 
  pad_beg = pad_total // 2
  pad_end = pad_total - pad_beg

  paddings[cnl_idx] = [pad_beg, pad_end]
  inputs = tf.pad(inputs, paddings)
  return inputs # 经过平均池化和填充后的输入

# # 从空间特征信息到通道信息
def standard_block_s2c(inputs, filters, is_training, strides, data_format):
  '''
  Standard Network Building Block, from spatial info to channel info 
  '''
  with tf.variable_scope(None, default_name='standard_block_s2c'):
    skip_connection = skip_align(inputs, filters, strides, data_format)#平均池化和填充
    inputs = batch_norm(inputs, training=is_training) #标准化
    inputs = conv2d_activation(inputs)# 激活函数ELU
    # 进行卷积
    inputs = sep_conv2d(
        inputs=inputs,
        filters=filters,
        kernel_size=3,
        strides=strides,
        padding='SAME',
        data_format=data_format)
    inputs = inputs + skip_connection # 残差连接
    return tf.identity(inputs, name='value')

# 从通道特征信息到空间信息
def standard_block_c2s(inputs, filters, is_training, strides, data_format):
  '''
  Standard Network Building Block, from channel info to spatial info
  '''
  with tf.variable_scope(None, default_name='standard_block_c2s'):# 默认使用自定义的standard_block_c2s块
    inputs = batch_norm(inputs, training=is_training)#标准化层
    inputs = conv2d_activation(inputs)#激活层
    # 卷积层
    inputs = conv2d(
        inputs=inputs, filters=filters, kernel_size=3, strides=strides, data_format=data_format)
    return tf.identity(inputs, name='value')

# 编码网络
def encrypter(orig_image, hide_image, is_training):
  '''
  Steganography Encrypter
  '''
  _, _, mncnls = params.MNROWS.value, params.MNCOLS.value, params.MNCNLS.value
  # 图像
  orig_image_shape = tf_utils.shape(orig_image)[1:4]
  hide_image_shape = tf_utils.shape(hide_image)[1:4]
  expc_shape = [params.MNROWS.value, params.MNCOLS.value, params.MNCNLS.value]
  assert orig_image_shape == expc_shape, \
      'Cover Image Dimension Error, Actual({}) != Expected({})'.format(
          orig_image_shape, expc_shape)
  assert hide_image_shape == expc_shape, \
      'Hidden Image Dimension Error, Actual({}) != Expected({})'.format(
          hide_image_shape, expc_shape)
  data_format = 'channels_first'

  with tf.variable_scope('encrypter'):
    with ts.arg_scope([conv2d], **conv2d_params), \
         ts.arg_scope([sep_conv2d], **sep_conv2d_params), \
         ts.arg_scope([batch_norm], **batch_norm_params):
      orig_image = tf.transpose(orig_image, [0, 3, 1, 2])
      hide_image = tf.transpose(hide_image, [0, 3, 1, 2])

      m = tf.concat([orig_image, hide_image], axis=1)

      m = standard_block_s2c(m, 32, is_training, 1, data_format)
      m = standard_block_s2c(m, 32, is_training, 1, data_format)
      m = standard_block_s2c(m, 64, is_training, 1, data_format)
      m = standard_block_s2c(m, 64, is_training, 1, data_format)
      m = standard_block_s2c(m, 128, is_training, 1, data_format)
      m = standard_block_s2c(m, 128, is_training, 1, data_format)

      m = standard_block_c2s(m, 32, is_training, 1, data_format)
      m = standard_block_c2s(m, mncnls, is_training, 1, data_format)

      m = tf.transpose(m, [0, 2, 3, 1], name='steg_image')

      return m


def decrypter(image, is_training):
  '''
  Steganography Decrypter
  '''
  _, _, mncnls = params.MNROWS.value, params.MNCOLS.value, params.MNCNLS.value

  steg_image_shape = tf_utils.shape(image)[1:4]
  expc_shape = [params.MNROWS.value, params.MNCOLS.value, params.MNCNLS.value]
  assert steg_image_shape == expc_shape, \
      'Stegged Image Dimension Error, Actual({}) != Expected({})'.format(
          steg_image_shape, expc_shape)
  data_format = 'channels_first'

  with tf.variable_scope('decrypter'):
    with ts.arg_scope([conv2d], **conv2d_params), \
         ts.arg_scope([sep_conv2d], **sep_conv2d_params), \
         ts.arg_scope([batch_norm], **batch_norm_params):
      m = image
      m = tf.transpose(m, [0, 3, 1, 2])

      m = standard_block_s2c(m, 32, is_training, 1, data_format)
      m = standard_block_s2c(m, 32, is_training, 1, data_format)
      m = standard_block_s2c(m, 64, is_training, 1, data_format)
      m = standard_block_s2c(m, 64, is_training, 1, data_format)
      m = standard_block_s2c(m, 128, is_training, 1, data_format)
      m = standard_block_s2c(m, 128, is_training, 1, data_format)

      m = standard_block_c2s(m, 32, is_training, 1, data_format)
      m = standard_block_c2s(m, mncnls, is_training, 1, data_format)

      m = tf.transpose(m, [0, 2, 3, 1], name='dcpt_image')

    return m
