import photosdl
import time
import sys, getopt
from os import listdir, remove
from os.path import isfile, join, exists


def main(argv):
    photo_dir = "./"
    url = ''
    port = ''
    username = ''
    password = ''

    try:
        opts, args = getopt.getopt(argv,"hu:p:U:P:d:",["username=","password=","url=","port=","directory="])
    except getopt.GetoptError:
        print ('filesync.py -u <username> -p <password> -U <url> -P <port> -d <dir>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ('filesync.py -u <username> -p <password> -U <url> -P <port> -d <dir>')
            sys.exit()
        elif opt in ("-u", "--username"):
            username = arg
        elif opt in ("-p", "--password"):
            password = arg
        elif opt in ("-U", "--url"):
            url = arg
        elif opt in ("-P", "--port"):
            port = arg
        elif opt in ("-d", "--directory"):
            photo_dir = arg


    current_files = [f for f in listdir(photo_dir) if isfile(join(photo_dir, f))]

    phdl = photosdl.Photos(url, port, username, password, secure=True, cert_verify=True, dsm_version=7, debug=True, otp_code=None)
    additional= ["thumbnail","resolution","orientation","video_convert","video_meta","address"]
    items = phdl.get_album_items('kitchen-dash', additional=additional)

    parsed_items = phdl.parse_items(items['data']['list'])

    if len(parsed_items) < 5:
        print("Only %s pictures, exiting" % len(parsed_items))
        return
    
    for cache_key, unit_id in parsed_items.items():
        if "%s.jpg" % cache_key in current_files:
            current_files.remove("%s.jpg" % cache_key)
        else:
            dl = phdl.download_item(cache_key=cache_key, unit_id=unit_id)
            with open("%s%s.jpg" % (photo_dir,cache_key), "wb") as binary_file:
                binary_file.write(dl.content)

    for current_file in current_files:
        if current_file[-4:] != ".jpg":
            continue
        filename = "%s%s" % (photo_dir,current_file)

        if exists(filename):
            remove(filename)

if __name__ == "__main__":
   main(sys.argv[1:])
   while True:
       time.sleep(1)