# coding=utf-8
import os
import sys
#importlib.reload(sys)
##sys.setdefaultencoding("utf-8")
import time
from flask import request, send_from_directory
from flask import Flask, request, redirect, url_for
import uuid
import tensorflow as tf
import numpy as np
#from classify_image import run_inference_on_image
from classify_image import NodeLookup

ALLOWED_EXTENSIONS = set(['jpg','JPG', 'jpeg', 'JPEG', 'png'])

FLAGS = tf.app.flags.FLAGS

tf.app.flags.DEFINE_string('model_dir', '', """Path to graph_def pb, """)
tf.app.flags.DEFINE_string('model_name', 'my_inception_v4_freeze.pb', '')
tf.app.flags.DEFINE_string('label_file', 'my_inception_v4_freeze.label', '')
tf.app.flags.DEFINE_string('upload_folder', '/tmp/', '')
tf.app.flags.DEFINE_integer('num_top_predictions', 5,
                            """Display this many predictions.""")
tf.app.flags.DEFINE_integer('port', '5001',
        'server with port,if no port, use deault port 80')

tf.app.flags.DEFINE_boolean('debug', False, '')

UPLOAD_FOLDER = FLAGS.upload_folder
ALLOWED_EXTENSIONS = set(['jpg','JPG', 'jpeg', 'JPEG', 'png'])

app = Flask(__name__)
app._static_folder = UPLOAD_FOLDER

def allowed_files(filename):
  return '.' in filename and \
      filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def rename_filename(old_file_name):
  basename = os.path.basename(old_file_name)
  name, ext = os.path.splitext(basename)
  new_name = str(uuid.uuid1()) + ext
  return new_name


def init_graph(model_name=FLAGS.model_name):
  with open(model_name, 'rb') as f:
    graph_def = tf.GraphDef()
    graph_def.ParseFromString(f.read())
    _ = tf.import_graph_def(graph_def, name='')

def run_inference_on_image(file_name):
  image_data = open(file_name, 'rb').read()
  sess = app.sess
  softmax_tensor = sess.graph.get_tensor_by_name('InceptionV4/Logits/Predictions:0')
  predictions = sess.run(softmax_tensor,
                           {'input:0': image_data})
  predictions = np.squeeze(predictions)

  # Creates node ID --> English string lookup.
  node_lookup = app.node_lookup
  top_k = predictions.argsort()[-FLAGS.num_top_predictions:][::-1]
  top_names = []
  for node_id in top_k:
    human_string = node_lookup.id_to_string(node_id)
    top_names.append(human_string)
    score = predictions[node_id]
    print('id:[%d] name:[%s] (score = %.5f)' % (node_id, human_string, score))
  return predictions, top_k, top_names

def inference(file_name):
  try:
    predictions, top_k, top_names = run_inference_on_image(file_name)
    print(predictions)
  except Exception as ex: 
    print(ex)
    return ""
  new_url = '/static/%s' % os.path.basename(file_name)
  image_tag = '<img src="%s"></img><p>'
  new_tag = image_tag % new_url
  format_string = ''
  for node_id, human_name in zip(top_k, top_names):
    score = predictions[node_id]
    format_string += '%s (score:%.5f)<BR>' % (human_name, score)
  ret_string = new_tag  + format_string + '<BR>' 
  return ret_string


@app.route("/", methods=['GET', 'POST'])
def root():
  result = """
    <!doctype html>
    <title>临时测试用</title>
    <h1>来喂一张照片吧</h1>
    <form action="" method=post enctype=multipart/form-data>
      <p><input type=file name=file value='选择图片'>
         <input type=submit value='上传'>
    </form>
    <p>%s</p>
    """ % "<br>"
  if request.method == 'POST':
    file = request.files['file']
    old_file_name = file.filename
    if file and allowed_files(old_file_name):
      filename = rename_filename(old_file_name)
      file_path = os.path.join(UPLOAD_FOLDER, filename)
      file.save(file_path)
      type_name = 'N/A'
      print('file saved to %s' % file_path)
      start_time = time.time()
      out_html = inference(file_path)
      duration = time.time() - start_time
      print('duration:[%.0fms]' % (duration*1000))
      return result + out_html 
  return result

if __name__ == "__main__":
  print('listening on port %d' % FLAGS.port)
  init_graph(model_name=FLAGS.model_name)
  label_file, _ = os.path.splitext(FLAGS.model_name)
  label_file = label_file + '.label'
  node_lookup = NodeLookup(label_file)
  app.node_lookup = node_lookup
  sess = tf.Session()
  app.sess = sess
  app.run(host='0.0.0.0', port=FLAGS.port, debug=FLAGS.debug, threaded=True)

