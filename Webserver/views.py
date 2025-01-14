import json
import os
import traceback
from datetime import datetime

from flask import jsonify, request, render_template, redirect, send_from_directory, abort, Blueprint, url_for

from werkzeug.utils import secure_filename
import uuid
import shutil

from auth_requests import *
from preview_builder import generate_plot_data
from data_factory import DataFactory

from authentication import basic_auth, token_auth, open_auth_requests
from tools import *




view = Blueprint('views', __name__, template_folder='templates', static_folder='static')


@view.app_template_filter()
def is_boolean(input):
    return type(input) is bool or input == 'True' or input == 'False' or input == 'on' or input == 'off'

@view.app_template_filter()
def is_number(input):
    return type(input) is int or (type(input) is str and input.isnumeric())


@view.app_template_filter()
def render_is_checked(input):
    if bool(input):
        return 'checked'
    return ''


@view.route('/')
def index():
    # return render_template('index.html')
    return redirect(url_for('views.list_recordings'))


@view.route('/tokenauth/request/')
def request_token():
    identifier = request.args.get('identifier')
    if identifier is None or identifier == '':
        return jsonify({'status': 'error', 'msg': 'no identifier'})

    auth_request: AuthRequest = open_auth_requests.get_request(identifier)
    if auth_request is None:
        open_auth_requests.new_request(identifier)
        return jsonify({'status': 'new', 'msg': 'created request'})

    else:
        if not auth_request.granted:
            return jsonify({'status': 'pending', 'msg': 'waiting for confirmation'})
        else:
            open_auth_requests.remove_request(auth_request)
            return jsonify({'status': 'grant', 'token': config.client_secret})


@view.route('/tokenauth/check/')
@basic_auth.login_required
def get_open_auth_requests():
    return render_template('list_requests.html', open_requests=open_auth_requests.open_auth_requests)


@view.route('/settings/', methods=['GET', 'POST'])
@basic_auth.login_required
def settings():
    if request.method == 'POST':
        print('Save new settings')
        settings_values = config.get_config_values().copy()
        for key in settings_values.keys():
            settings_values[key] = request.form.get(key)
            print("save ", key, settings_values[key])
            if is_boolean(settings_values[key]):
                settings_values[key] = bool(settings_values[key])
            if settings_values[key] is None and is_boolean(config.get_config_values()[key]):
                settings_values[key] = False
            if is_number(settings_values[key]):
                print("save as number")
                settings_values[key] = int(settings_values[key])
        print(settings_values)
        config.save_config(settings_values)

    return render_template('settings.html', setting_entries=config.get_config_values())


@view.route('/tfmodel/', methods=['GET', 'POST'])
@basic_auth.login_required
def tfmodel():
    upload_info_text = None
    upload_error_text = None
    sensors = {1: 'ACCELEROMETER', 4: 'GYROSCOPE', 2: 'MAGNETIC FIELD', 11: 'ROTATION VECTOR'}
    filename = "tf_settings"

    old_settings = dict()
    old_settings_file = get_tf_model_settings_file()
    if old_settings_file is not None:
        with open(os.path.join(TFMODEL_FOLDER, old_settings_file)) as json_file:
            old_settings = json.load(json_file)
        filename = os.path.splitext(old_settings_file)[0]

    if request.method == 'POST':
        print('Save new tf model', request.form)
        do_save_file = True
        if 'file' not in request.files:
            upload_error_text = 'Info: no new file was selected'
        else:
            file = request.files['file']
            # if user does not select file, browser also
            # submit an empty part without filename
            if file.filename == '':
                upload_error_text = 'Info: no new file was selected'
            else:
                if file and is_allowed_file(file.filename):
                    filename = os.path.splitext(secure_filename(file.filename))[0]
                    file_extension = os.path.splitext(secure_filename(file.filename))[1]
                    file_path = os.path.join(TFMODEL_FOLDER, filename + file_extension)
                    if file_extension == '.ort':
                        missing_optypes = check_valid_ort_model(file.read())
                        if len(missing_optypes) > 0:
                            upload_error_text = 'Error: Missing operations: ' + str(missing_optypes)
                            do_save_file = False
                    if do_save_file:
                        file.seek(0)
                        file.save(file_path)
                        upload_info_text = 'Uploaded ' + filename

                else:
                    upload_error_text = 'Error: no valid file'

        settings_dict = dict()
        settings_dict['frame_size'] = int(request.form.get('frameSizeInput'))
        settings_dict['mean_threshold'] = float(request.form.get('meanThresholdInput'))
        settings_dict['mean_kernel_size'] = int(request.form.get('meanKernelWidthInput'))
        settings_dict['notification_cool_down'] = int(request.form.get('notificationCoolDownInput'))
        required_sensors = request.form.getlist('requiredSensorsSelect')
        for i in range(len(required_sensors)):
            required_sensors[i] = int(required_sensors[i])
        settings_dict['required_sensors'] = required_sensors
        old_settings = settings_dict

        if do_save_file:
            with open(os.path.join(TFMODEL_FOLDER, filename + '.json'), 'w') as outfile:
                json.dump(settings_dict, outfile)
            if upload_info_text is None:
                upload_info_text = 'Saved new settings'
            else:
                upload_info_text = 'Saved new settings and model ' + filename

    newest_tf_file = find_newest_tf_file()
    all_model_files = list()
    all_model_file_paths = list()
    all_model_settings = list()
    for file in os.listdir(TFMODEL_FOLDER):
        if '.tflite' not in file and '.ort' not in file:
            continue
        all_model_files.append(file)
        all_model_file_paths.append(file)
        settings_name = os.path.splitext(file)[0] + '.json'
        all_model_settings.append(settings_name)

    return render_template('tfmodel.html', upload_info_text=upload_info_text, upload_error_text=upload_error_text,
                           sensors=sensors, old_settings=old_settings, all_model_files=all_model_files,
                           all_model_file_paths=all_model_file_paths, all_model_settings=all_model_settings,
                           newest_tf_file=newest_tf_file)


@view.route('/tfmodel/select/<string:tf_model>/')
@basic_auth.login_required
def select_tfmodel(tf_model):
    tf_file = os.path.join(TFMODEL_FOLDER, tf_model)
    print('tf file:', tf_file)
    if os.path.exists(tf_file):
        os.utime(tf_file, None)
        print('update time')
    settings_file = os.path.join(TFMODEL_FOLDER, os.path.splitext(tf_model)[0] + '.json')
    if os.path.exists(settings_file):
        os.utime(settings_file, None)
    return redirect(url_for('views.tfmodel'))


@view.route('/tokenauth/grant/<int:auth_id>/')
@basic_auth.login_required
def grant_auth_request(auth_id):
    auth_request = open_auth_requests.get_by_id(auth_id)
    if auth_request is not None:
        auth_request.granted = True
    return redirect(url_for('views.get_open_auth_requests'))


@view.route('/recording/list/')
@basic_auth.login_required
def list_recordings():
    recording_directories = os.listdir(RECORDINGS_FOLDER)
    recording_infos = dict()
    filter_args = {}
    if len(request.args) > 0:
        filter_args = request.args.to_dict(flat=True)

    for directory in recording_directories:

        short_description = ""
        long_description = ""
        description_file = os.path.join(RECORDINGS_FOLDER, os.path.join(directory, "README.md"))
        if os.path.exists(description_file):
            with open(description_file, 'r') as desc_file:
                short_description = desc_file.readline()
                long_description = short_description + desc_file.read()
        changed_time_stamp = os.stat(os.path.join(RECORDINGS_FOLDER, directory)).st_ctime

        # since directories creation time changes if a file was edited, we have to find the oldest file within them
        meta_info_file = None
        for file in os.listdir(os.path.join(RECORDINGS_FOLDER, directory)):
            if os.path.splitext(file)[1] == '.json' and 'metaInfo' in file:
                meta_info_file = os.path.join(RECORDINGS_FOLDER, os.path.join(directory, file))
            tmp_c_time = os.stat(os.path.join(RECORDINGS_FOLDER, os.path.join(directory, file))).st_ctime
            if tmp_c_time < changed_time_stamp:
                changed_time_stamp = tmp_c_time

        meta_info = {}
        if meta_info_file is not None:
            with open(meta_info_file) as json_file:
                meta_info = json.load(json_file)
        meta_info['description'] = long_description

        skip_session = False
        for filter_arg, arg_value in filter_args.items():
            if filter_arg not in meta_info or str(arg_value) not in str(meta_info[filter_arg]):
                skip_session = True
        if skip_session:
            continue

        session_size = get_session_size(os.path.join(RECORDINGS_FOLDER, directory))
        change_time_string = datetime.fromtimestamp(changed_time_stamp).strftime('%d/%m/%Y, %H:%M:%S')
        recording_infos[directory] = [change_time_string, changed_time_stamp, short_description,
                                      convert_size(session_size), get_size_color(session_size), meta_info]

    recordings_sort = sorted(recording_infos.keys(), key=lambda key: recording_infos[key][1], reverse=True)

    # recording_directories = [x[0] for x in os.walk(RECORDINGS_FOLDER)]

    return render_template('list_recordings.html', recordings=recording_infos, sorting=recordings_sort,
                           current_filter=filter_args)

@view.route('/recording/get/<string:recording>/')
@basic_auth.login_required
def get_recording(recording):
    recording_files = []
    description = ""
    path = os.path.join(RECORDINGS_FOLDER, recording)
    total_size = 0
    meta_info_file = None
    for file in os.listdir(path):
        if os.path.splitext(file)[1] == '.json' and 'metaInfo' in file:
            meta_info_file = os.path.join(path, file)
        total_size += os.path.getsize(os.path.join(path, file))
        if config.hide_mic_files and '.zip' in file and contains_mic_files(file, path):
            continue
        if file == 'README.md':
            description = open(os.path.join(RECORDINGS_FOLDER, os.path.join(recording, "README.md")), 'r').read()
        recording_files.append(file)

    meta_info = {}
    if meta_info_file is not None:
        with open(meta_info_file) as json_file:
            meta_info = json.load(json_file)

    sensor_data_file = None
    sensor_data_flattened_file = None
    generated_data_size = 0
    data_file = os.path.join(path, DataFactory.sensor_data_file_name)
    if os.path.exists(data_file):
        sensor_data_file = os.path.join(recording, DataFactory.sensor_data_file_name)
        generated_data_size += os.path.getsize(data_file)
    data_file = os.path.join(path, DataFactory.sensor_data_flattened_file_name)
    if os.path.exists(data_file):
        sensor_data_flattened_file = os.path.join(recording, DataFactory.sensor_data_flattened_file_name)
        generated_data_size += os.path.getsize(data_file)

    total_size = convert_size(total_size)
    generated_data_size = convert_size(generated_data_size)
    return render_template('show_recording.html', recording_name=recording, files=recording_files,
                           description=description, total_size=total_size, sensor_data_file=sensor_data_file,
                           sensor_data_flattened_file=sensor_data_flattened_file,
                           generated_data_size=generated_data_size, meta_info=meta_info)


@view.route('/recording/plot/<string:recording>/')
@basic_auth.login_required
def plot_recording(recording):
    plot_file = os.path.join(os.path.join(RECORDINGS_FOLDER, recording), 'data_plot.svg')
    if not os.path.exists(plot_file):
        plot_file = os.path.join(os.path.join(RECORDINGS_FOLDER, recording), 'data_plot.png')
        if not os.path.exists(plot_file):
            try:
                generate_plot_data(os.path.join(RECORDINGS_FOLDER, recording))
            except Exception as e:
                traceback.print_tb(e.__traceback__)
                return render_template('error_show_recording_plot.html', recording_name=recording, error=e, traceback=traceback.format_exc())

    if os.path.exists(plot_file):
        if recording not in prepared_plot_data.copy():
            try:
                get_plot_data(recording)
            except Exception as e:
                traceback.print_tb(e.__traceback__)
                return render_template('error_show_recording_plot.html', recording_name=recording, error=e, traceback=traceback.format_exc())
        plot_file = os.path.join(recording, 'data_plot.png')
        return render_template('show_recording_plot.html', recording_name=recording, plot=plot_file)

    return render_template('error_show_recording_plot.html', recording_name=recording)


@view.route('/recording/clean/<string:recording>/')
@basic_auth.login_required
def clean_recording(recording):
    recording_path = os.path.join(RECORDINGS_FOLDER, recording)
    clean_session_directory(recording_path)
    return redirect(url_for('views.get_recording', recording=recording))


@view.route('/recording/new/', methods=['GET', 'POST'])
@token_auth.login_required
def new_recording():
    # secret_token = request.args.get('token')
    # if secret_token is None or secret_token != config.client_secret:
    #     return jsonify({'status': 'not authenticated'})

    print('User: ', token_auth.current_user())

    if request.method == 'GET':
        new_uuid = uuid.uuid4()
        print('Deliver new uuid:', new_uuid)
        return jsonify({'status': 'success', 'uuid': new_uuid})
    elif request.method == 'POST':
        print('Get new records')
        request_uuid = request.args.get('uuid')
        print('Id: ', request_uuid)
        if request_uuid is None or request_uuid == '':
            print('No uuid')
            return jsonify({'status': 'error, now uuid'})
        if 'file' not in request.files:
            print('No file part')
            return jsonify({'status': 'error, now file'})
        file = request.files['file']
        if file.filename == '':
            print('No selected file')
            return jsonify({'status': 'error, now selected file'})
        if file and is_allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if config.rename_mic_files and 'mic' in filename and '.zip' in filename:
                numbering = filename.split('_')[-1]
                filename = generate_random_string(16) + '_' + numbering
            upload_path = os.path.join(RECORDINGS_FOLDER, request_uuid)
            if not os.path.isdir(upload_path):
                os.mkdir(upload_path)
                description_file = open(os.path.join(upload_path, "README.md"), 'x')

            file.save(os.path.join(upload_path, filename))
            add_file_to_zip(filename, upload_path, request_uuid)
            return jsonify({'status': 'success, uploaded ' + file.filename})

        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'})


@view.route('/recording/delete/<string:recording>/')
@basic_auth.login_required
def delete_recording(recording):
    file = os.path.join(RECORDINGS_FOLDER, recording)
    if os.path.exists(file):
        shutil.rmtree(file)
    return redirect(url_for('views.list_recordings'))


@view.route('/recordingfile/delete/<string:recording>/<string:file_name>/')
@basic_auth.login_required
def delete_recording_file(recording, file_name):
    file = os.path.join(RECORDINGS_FOLDER, os.path.join(recording, file_name))
    if os.path.exists(file):
        os.remove(file)
    return redirect(url_for('views.get_recording', recording=recording))


@view.route('/recording/description/<string:recording>/', methods=['GET', 'POST'])
@basic_auth.login_required
def recording_description(recording):
    print('User: ', token_auth.current_user())

    description_file_path = os.path.join(RECORDINGS_FOLDER, os.path.join(recording, "README.md"))

    if request.method == 'GET':
        description_file = open(description_file_path, 'r')
        return jsonify({'description': description_file.read()})
    elif request.method == 'POST':
        print('Get new description')
        new_description = request.form.get('description')
        description_file = open(description_file_path, 'w')
        description_file.write(new_description)
        description_file.close()

    return redirect(url_for('views.get_recording', recording=recording))


@view.route('/recording/data/<string:recording>/')
def recording_data(recording):
    print('User: ', token_auth.current_user())
    plot_data = get_plot_data(recording)

    start_point = float(request.args.get('start'))
    end_point = float(request.args.get('end'))

    series = plot_data.get_series(start_point, end_point)

    # series.append(plot_data.annotations)
    # series.append(plot_data.time_stamp_series)

    # print(time_stamp_series)
    return jsonify(series)
    # return jsonify({'data': {'series': series, 'annotations': prepared_plot_data[recording].annotations}})
    # return jsonify({'data': {'series': series}})



@view.route('/recording/series/<string:recording>/')
def recording_series(recording):
    print('User: ', token_auth.current_user())
    plot_data = get_plot_data(recording)

    start_point = float(request.args.get('start'))
    end_point = float(request.args.get('end'))

    series = plot_data.get_series(start_point, end_point)

    # series.append(plot_data.annotations)
    # series.append(plot_data.time_stamp_series)

    # print(time_stamp_series)

    return jsonify({'data': {'series': series, 'annotations': prepared_plot_data[recording].annotations}})
    # return jsonify({'data': {'series': series}})


@view.route('/recording/np/generate/<string:recording>/')
def generate_numpy_data(recording):
    data_factory = DataFactory(recording, os.path.join(RECORDINGS_FOLDER, recording))
    data_factory.generate_np_sensor_data_file()
    return redirect(url_for('views.get_recording', recording=recording))


@view.route('/recording/np/delete/<string:recording>/')
def delete_numpy_data(recording):
    path = os.path.join(RECORDINGS_FOLDER, recording)
    os.remove(os.path.join(path, DataFactory.sensor_data_file_name))
    os.remove(os.path.join(path, DataFactory.sensor_data_flattened_file_name))
    return redirect(url_for('views.get_recording', recording=recording))


@view.route('/tfmodel/get/latest/')
def get_latest_tf_model():
    if not os.path.exists(TFMODEL_FOLDER):
        abort(404, description="Resource not found")

    latest_model = find_newest_tf_file()

    print("found file ", latest_model)
    if latest_model is not None:
        return send_from_directory(TFMODEL_FOLDER, path=latest_model, as_attachment=True)
    abort(404, description="Resource not found")


@view.route('/tfmodel/get/settings/')
def get_latest_tf_model_settings():
    latest_model_settings = get_tf_model_settings_file()

    print("found file ", latest_model_settings)
    if latest_model_settings is not None:
        return send_from_directory(TFMODEL_FOLDER, path=latest_model_settings, as_attachment=True)
    abort(404, description="Resource not found")


@view.route('/tfmodel/check/latest/')
def check_latest_tf_model():
    if not os.path.exists(TFMODEL_FOLDER):
        abort(404, description="Resource not found")

    latest_model = find_newest_tf_file()

    print("found file ", latest_model)
    if latest_model is not None:
        return jsonify({'activeModel': latest_model})
    abort(404, description="Resource not found")


@view.route("/auth")
@basic_auth.login_required
def nginx_auth():
    if basic_auth.get_auth():
        return 'Authentication granted'
    else:
        return 'Not authorized', 401


# just for debug
@view.route('/static/<path:path>')
def send_js(path):
    return send_from_directory('js', path)


@view.route('/uploads/recordings/<path:path>')
def uploaded_recording_file(path):
    return send_from_directory(RECORDINGS_FOLDER, path)


@view.route('/uploads/tf_models/<path:path>')
def uploaded_tf_file(path):
    return send_from_directory(TFMODEL_FOLDER, path)
