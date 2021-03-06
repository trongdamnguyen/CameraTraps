'''
copy_and_unzip_emammal.py

Siyu Yang

Script to copy all deployments in the emammal container (mounted on the VM or not) to data
disk at /datadrive and unzip them, deleting the copied zip file.

Need to add exception handling.
'''

#%% Imports and constants

import json
import os
import zipfile
from datetime import datetime
from tqdm import tqdm
from azure.storage.blob import BlockBlobService

import itertools
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool  # this functions like threading
from shutil import copy, copyfile

# configurations and paths
log_folder = '/home/yasiyu/yasiyu_log'
dest_folder = '/datadrive/emammal'  # data disk attached where data is stored
origin = 'cloud'  # 'cloud' or 'mounted'


#%% Helper functions

def _copy_unzip(source_path, dest_folder):
    
    try:
        dest_subfolder = os.path.join(dest_folder, os.path.basename(source_path).split('.zip')[0])
        if os.path.exists(dest_subfolder):
            print('{} exists.'.format(dest_subfolder))
            return('exists')

        print('Copying...')
        # dest_path = copy(source_path, dest_folder)
        dest_path = os.path.join(dest_folder, os.path.basename(source_path))
        copyfile(source_path, dest_path)

        with zipfile.ZipFile(dest_path, 'r') as zip_ref:
            zip_ref.extractall(dest_subfolder)

        os.remove(dest_path)
        print('{} copied and extracted'.format(dest_subfolder))
        return None

    except Exception:
        try:
            print('Retrying...')
            dest_path = os.path.join(dest_folder, os.path.basename(source_path))
            copyfile(source_path, dest_path)
            with zipfile.ZipFile(dest_path, 'r') as zip_ref:
                zip_ref.extractall(dest_subfolder)
            os.remove(dest_path)
            print('{} copied and extracted'.format(dest_subfolder))
            return (None)
        except Exception as e:
            print('WARNING {} did not get copied. Exception: {}'.format(source_path, str(e)))
            return source_path


def copy_from_mounted_container(source_folder, dest_folder):
    
    sources = []

    collections = sorted(os.listdir(source_folder))

    for collection in collections:
        collection_folder = os.path.join(source_folder, collection)
        if not os.path.isdir(collection_folder):
            continue

        print('Processing collection {}'.format(collection))

        for file in tqdm(sorted(os.listdir(collection_folder))):
            source_path = os.path.join(collection_folder, file)
            sources.append(source_path)

    # num_workers = multiprocessing.cpu_count()
    # pool = ThreadPool(num_workers)
    # results = pool.starmap(_copy_unzip, zip(sources, itertools.repeat(dest_folder)))
    #
    # print('Waiting for processes to finish...')
    # pool.close()
    # pool.join()

    # sequential
    results = []
    for source_path in sources:
        result = _copy_unzip(source_path, dest_folder)
        results.append(result)

    cur_time = datetime.now().strftime('%Y%m%d-%H%M%S')
    with open(os.path.join(log_folder, 'copy_unzip_results_{}.json'.format(cur_time)), 'w') as f:
        json.dump(results, f)


def _download_unzip(blob_service, blob_path, dest_path):
    try:
        print('Downloading...')
        blob_service.get_blob_to_path(container, blob_path, dest_path)

        dest_subfolder = dest_path.split('.zip')[0]

        with zipfile.ZipFile(dest_path, 'r') as zip_ref:
            zip_ref.extractall(dest_subfolder)

        os.remove(dest_path)
        print('{} copied and extracted'.format(dest_subfolder))
        return None

    except Exception as e:
        print('ERROR while downloading or unzipping {}. Exception: {}'.format(blob_path, str(e)))
        return blob_path


def download_from_container(dest_folder, blob_service, container='emammal', desired_blob_prefix=''):
    generator = blob_service.list_blobs(container)
    desired_blobs = [blob.name for blob in generator if blob.name.startswith(desired_blob_prefix)]

    results = []
    for blob_path in tqdm(desired_blobs):
        blob_name = blob_path.split('/')[1]
        dest_path = os.path.join(dest_folder, blob_name)
        result = _download_unzip(blob_service, blob_path, dest_path)
        results.append(result)

    cur_time = datetime.now().strftime('%Y%m%d-%H%M%S')
    with open(os.path.join(log_folder, 'download_unzip_results_{}.json'.format(cur_time)), 'w') as f:
        json.dump(results, f)


#%% Command-line driver
        
if __name__ == '__main__':
    if origin == 'cloud':
        container = 'emammal'
        desired_blob_prefix = '0Robert Long/'

    print('Start timing...')
    start_time = datetime.now()

    if origin == 'mounted':
        # if the blob container is already mounted on the VM
        source_folder = '/home/yasiyu/mnt/wildlifeblobssc/emammal'  # blob container mounted
        copy_from_mounted_container(source_folder, dest_folder)

    elif origin == 'cloud':
        # or you can download them using the storage Python SDK
        # key to the storage account should be stored in the environment variable AZ_STORAGE_KEY
        key = os.environ["AZ_STORAGE_KEY"]
        blob_service = BlockBlobService(account_name='wildlifeblobssc', account_key=key)
        download_from_container(dest_folder, blob_service, container=container,
                                desired_blob_prefix=desired_blob_prefix)

    print('Process took {}.'.format(datetime.now() - start_time))
