# -*- coding: utf-8 -*-

from functools import reduce
import sys, platform
import time, os, json, re, datetime, math, operator
import concurrent.futures
import requests
import argparse
from pathlib import Path

if platform.system() == 'Windows':
    if operator.ge(*map(lambda version: list(map(int, version.split('.'))), [platform.version(), '10.0.14393'])):
        os.system('')
    else:
        import colorama
        colorama.init()

try:
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
except:
    pass

parser = argparse.ArgumentParser(
    prog = 'weiboPicDownloader'
)
group = parser.add_mutually_exclusive_group(required = True)
group.add_argument(
    '-u', metavar = 'user', dest = 'users', nargs = '+',
    help = 'specify nickname or id of weibo users'
)
group.add_argument(
    '-f', metavar = 'file', dest = 'files', nargs = '+',
    help = 'import list of users from files'
)
parser.add_argument(
    '-d', metavar = 'directory', dest = 'directory',
    help = 'set picture saving path'
)
parser.add_argument(
    '-s', metavar = 'size', dest = 'size',
    default = 20, type = int,
    help = 'set size of thread pool'
)
parser.add_argument(
    '-r', metavar = 'retry', dest = 'retry',
    default = 5, type = int,
    help = 'set maximum number of retries'
)
parser.add_argument(
    '-i', metavar = 'interval', dest = 'interval',
    default = 1, type = float,
    help = 'set interval for feed requests'
)
parser.add_argument(
    '-c', metavar = 'cookie', dest = 'cookie',
    help = 'set cookie if needed'
)
parser.add_argument(
    '-b', metavar = 'boundary', dest = 'boundary',
    default = ':',
    help = 'focus on weibos in the id range'
)
parser.add_argument(
    '-R', metavar = 'resource', dest = 'resource',
    help = 'use dumped resource'
)
parser.add_argument(
    '-n', metavar = 'name', dest = 'name', default = '{name}',
    help = 'customize naming format'
)
parser.add_argument(
    '-v', dest = 'video', action = 'store_true',
    help = 'download videos together'
)
parser.add_argument(
    '-o', dest = 'overwrite', action = 'store_true',
    help = 'overwrite existing files'
)

def nargs_fit(parser, args):
    flags = parser._option_string_actions
    short_flags = [flag for flag in flags.keys() if len(flag) == 2]
    long_flags = [flag for flag in flags.keys() if len(flag) > 2]
    short_flags_with_nargs = set([flag[1] for flag in short_flags if flags[flag].nargs])
    short_flags_without_args = set([flag[1] for flag in short_flags if flags[flag].nargs == 0])
    validate = lambda part : (re.match(r'-[^-]', part) and (set(part[1:-1]).issubset(short_flags_without_args) and '-' + part[-1] in short_flags)) or (part.startswith('--') and part in long_flags)

    greedy = False
    for index, arg in enumerate(args):
        if arg.startswith('-'):
            valid = validate(arg)
            if valid and arg[-1] in short_flags_with_nargs:
                greedy = True
            elif valid:
                greedy = False
            elif greedy:
                args[index] = ' ' + args[index]
    return args

class printer():
    def __init__(self):
        self.pinned = False

    def print_fit(self, string, pin=False):
        if pin == True:            
            print(f'\r\033[K{string}', end='')
            self.pinned = True
        else:
            if self.pinned:
                print()
            print(string)
            self.pinned = False

print_fit = printer().print_fit

def merge(*dicts):
    result = {}
    for dictionary in dicts: result.update(dictionary)
    return result

def quit(string = ''):
    print_fit(string)
    exit()

def make_dir(path):
    try:
        os.makedirs(path)
    except Exception as e:
        quit(str(e))

def confirm(message):
    while True:
        answer = input('{} [Y/n] '.format(message)).strip()
        if answer == 'y' or answer == 'Y':
            return True
        elif answer == 'n' or answer == 'N':
            return False
        print_fit('unexpected answer')

def progress(part, whole, percent = False):
    if percent:
        return '{}/{}({}%)'.format(part, whole, int(float(part) / whole * 100))
    else:
        return '{}/{}'.format(part, whole)

def request_fit(method, url, max_retry = 0, cookie = None, stream = False):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 9; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.80 Mobile Safari/537.36',
        'Cookie': cookie
    }
    return requests.request(method, url, headers = headers, timeout = 5, stream = stream, verify = False)

def read_from_file(path):
    try:
        with open(path, 'r', encoding='gb18030', errors='ignore') as f:
            empty = []
            str = [line.strip() for line in f]
            for uncode in str:
                empty.append(uncode[0:10])
            return empty
    except Exception as e:
        quit(str(e))

def nickname_to_uid(nickname, token):
    url = 'https://m.weibo.cn/n/{}'.format(nickname)
    response = request_fit('GET', url, cookie = token)
    if re.search(r'/u/\d{10}$', response.url):
        return response.url[-10:]
    else:
        return

def uid_to_nickname(uid, token):
    url = 'https://m.weibo.cn/api/container/getIndex?type=uid&value={}'.format(uid)
    response = request_fit('GET', url, cookie = token)
    try:
        return json.loads(response.text)['data']['userInfo']['screen_name']
    except:
        return

def bid_to_mid(string):
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    alphabet = {x: n for n, x in enumerate(alphabet)}

    splited = [string[(g + 1) * -4 : g * -4 if g * -4 else None] for g in reversed(range(math.ceil(len(string) / 4.0)))]
    convert = lambda s : str(sum([alphabet[c] * (len(alphabet) ** k) for k, c in enumerate(reversed(s))])).zfill(7)
    return int(''.join(map(convert, splited)))

def parse_date(text):
    now = datetime.datetime.now()
    if '前' in text:
        if '小时' in text:
            return (now - datetime.timedelta(hours = int(re.search(r'\d+', text).group()))).date()
        else:
            return now.date()
    elif '昨天' in text:
        return now.date() - datetime.timedelta(days = 1)
    elif re.search(r'^[\d|-]+$', text):
        return datetime.datetime.strptime(((str(now.year) + '-') if not re.search(r'^\d{4}', text) else '') + text, '%Y-%m-%d').date()

def compare(standard, operation, candidate):
    for target in candidate:
        try:
            result = '>=<'
            if standard > target: result = '>'
            elif standard == target: result = '='
            else: result = '<'
            return result in operation
        except TypeError:
            pass

def get_resources(uid, video, interval, limit, token):
    page = 1
    size = 25
    amount = 0
    total = 0
    empty = 0
    aware = 1
    exceed = False
    resources = []

    newest_bid = ''

    while empty < aware and not exceed:
        try:
            url = 'https://m.weibo.cn/api/container/getIndex?count={}&page={}&containerid=107603{}'.format(size, page, uid)
            response = request_fit('GET', url, cookie = token)
            assert response.status_code != 418
            json_data = json.loads(response.text)
        except AssertionError:
            print_fit('punished by anti-scraping mechanism (#{})'.format(page), pin = True)
            empty = aware
        except Exception:
            pass
        else:
            empty = empty + 1 if json_data['ok'] == 0 else 0
            if total == 0 and 'cardlistInfo' in json_data['data']: total = json_data['data']['cardlistInfo']['total']
            cards = json_data['data']['cards']
            for card in cards:
                if 'mblog' in card:
                    mblog = card['mblog']
                    if 'isTop' in mblog and mblog['isTop']: continue
                    mid = int(mblog['mid'])
                    date = parse_date(mblog['created_at'])
                    mark = {'uid': uid, 'mid': mid, 'bid': mblog['bid'], 'date': date, 'text': mblog['raw_text']}
                    amount += 1
                    if not newest_bid: #Save newest bid
                        newest_bid = mblog['bid']              
                    if compare(limit[0], '>=', [mid, date]): exceed = True
                    if compare(limit[0], '>=', [mid, date]) or compare(limit[1], '<', [mid, date]): continue
                    if 'pics' in mblog:
                        if mblog['pic_num'] > 9:  # More than 9 images
                          
                            blog_url = card['scheme']
                            print_fit(f'Find more than 9 pictures for {blog_url}!')
                            with requests.get(blog_url) as r:
                                a = re.search(r'var \$render_data = \[(.+)\]\[0\] \|\| {};', r.text, flags=re.DOTALL)[1]
                                my_json = json.loads(a)
                                pics = my_json['status']['pics']
                        else:
                            pics = mblog['pics']                        
                        for index, pic in enumerate(pics, 1):
                            if 'large' in pic:
                                resources.append(merge({'url': pic['large']['url'], 'index': index, 'type': 'photo'}, mark))
                    elif 'page_info' in mblog and video:
                        if 'media_info' in mblog['page_info']:
                            media_info = mblog['page_info']['media_info']
                            streams = [media_info[key] for key in ['mp4_720p_mp4', 'mp4_hd_url', 'mp4_sd_url', 'stream_url'] if key in media_info and media_info[key]]
                            if streams:
                                resources.append(merge({'url': streams.pop(0), 'type': 'video'}, mark))
            print_fit('{} {}(#{})'.format('Analysing weibos...' if empty < aware and not exceed else 'finish analysis', progress(amount, total), page), pin = True)
            page += 1
        finally:
            time.sleep(interval)

    print_fit('Practically scanned {} weibos, get {} {}'.format(amount, len(resources), 'resources' if video else 'pictures'))
    # with open(f"json_backup/{uid}.json", "w", encoding='utf-8') as f1:
    #     json.dump(resources, f1, indent=2, default=json_serial)
    return resources, newest_bid

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime.date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def format_name(item, template):
    item['name'] = re.sub(r'\?\S+$', '', re.sub(r'^\S+/', '', item['url']))

    def safeify(name):
        template = {u'\\': u'＼', u'/': u'／', u':': u'：', u'*': u'＊', u'?': u'？', u'"': u'＂', u'<': u'＜', u'>': u'＞', u'|': u'｜'}
        for illegal in template:
            name = name.replace(illegal, template[illegal])
        return name

    def substitute(matched):
        key = matched.group(1).split(':')
        if key[0] not in item:
            return ':'.join(key)
        elif key[0] == 'date':
            return item[key[0]].strftime(key[1]) if len(key) > 1 else str(item[key[0]])
        elif key[0] == 'index':
            return str(item[key[0]]).zfill(int(key[1] if len(key) > 1 else '0'))
        elif key[0] == 'text':
            value = item[key[0]]
            value = value.replace('<br />', ' ') # Replace newline with space
            # value = re.sub(r'<.*?>', '', value) # Remove other HTML tags.
            value = value.replace('無断転載禁止', '')
            value = value.replace('\u200b', '')
            value = re.sub(r'#(.+?)(\[?超话\]?)?#', r' \1 ', value)
            value = re.sub(r'\s+', ' ', value)
            value = value.strip()[:100]
            return value
        else:
            return str(item[key[0]])
  
    return safeify(re.sub(r'{(.*?)}', substitute, template))

def download(url, path, overwrite):
    path = Path(path)
    if path.exists() and not overwrite: return True
    try:
        with request_fit('GET', url, stream = True) as response:
            expected_size = int(response.headers['Content-length'])
            with open(path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        size = path.stat().st_size
        if size != expected_size:
            raise Exception(f'{path.name.split(" ")[-1]}: filesize doesn\'t match header ({expected_size} -> {size}). Re-download...')            
    except Exception as ex:
        print_fit(ex)
        if path.exists():
            i = 1
            path_temp = path.with_name(f'[broken {i}]' + path.name)
            while path_temp.exists(): 
                i += 1
                path_temp = path.with_name(f'[broken {i}]' + path.name)
            path.rename(path_temp)
        return False
    else:
        return True


def main(*paras):
    if paras:
        args = parser.parse_args(nargs_fit(parser, paras))
    else:
        args = parser.parse_args(nargs_fit(parser, sys.argv[1:]))
    if args.users:
        users = args.users
    elif args.files:
        users = [read_from_file(path.strip()) for path in args.files]
        users = reduce(lambda x, y : x + y, users)
    users = [user.strip() for user in users]

    if args.directory:
        base = args.directory
        if os.path.exists(base):
            if not os.path.isdir(base): quit('saving path is not a directory')
        elif confirm('directory "{}" doesn\'t exist, help to create?'.format(base)):
            make_dir(base)
        else:
            quit('do it youself :)')
    else:
        base = os.path.join(os.path.dirname(__file__), 'weiboPic')
        if not os.path.exists(base): make_dir(base)

    boundary = args.boundary.split(':')
    boundary = boundary * 2 if len(boundary) == 1 else boundary
    numberify = lambda x: int(x) if re.search(r'^\d+$', x) else bid_to_mid(x)
    dateify = lambda t: datetime.datetime.strptime(t, '@%Y%m%d').date()
    parse_point = lambda p: dateify(p) if p.startswith('@') else numberify(p)
    try:
        boundary[0] = 0 if boundary[0] == '' else parse_point(boundary[0])
        boundary[1] = float('inf') if boundary[1] == '' else parse_point(boundary[1])
        if boundary[0] == boundary[1]:
            if type(boundary[0]) == int:
                boundary[0] = boundary[0] - 1
            else:
                boundary[0] = boundary[0] - datetime.timedelta(days = 1)
        if type(boundary[0]) == type(boundary[1]): assert boundary[0] <= boundary[1]
    except:
        quit('invalid id range {}'.format(args.boundary))

    token = 'SUB={}'.format(args.cookie) if args.cookie else None
    pool = concurrent.futures.ThreadPoolExecutor(max_workers = args.size)

    newest_bid = ''
    for number, user in enumerate(users, 1):
        
        print_fit('{}/{} {}'.format(number, len(users), time.ctime()))
        
        if re.search(r'^\d{10}$', user):
            nickname = uid_to_nickname(user, token)
            uid = user
        else:
            nickname = user
            uid = nickname_to_uid(user, token)

        if not nickname or not uid:
            print_fit('Invalid account {}'.format(user))
            print_fit('-' * 30)
            continue

        print_fit('{} {}'.format(nickname, uid))

        if args.resource:
            with open(args.resource, 'r', encoding='utf-8') as f:
                resources = json.load(f)
        else:
            try:
                resources, newest_bid = get_resources(uid, args.video, args.interval, boundary, token)
            except KeyboardInterrupt:
                quit()

        # quit()
        album = os.path.join(base, nickname)
        if resources and not os.path.exists(album): make_dir(album)
        retry = 0
        while resources and retry <= args.retry:
            
            if retry > 0: print_fit('Automatic retry {}'.format(retry))

            total = len(resources)
            tasks = []
            done = 0
            failed = {}
            cancel = False

            for resource in resources:
                path = os.path.join(album, format_name(resource, args.name))
                tasks.append(pool.submit(download, resource['url'], path, args.overwrite))

            while done != total:
                try:
                    done = 0
                    for index, task in enumerate(tasks):
                        if task.done() == True:
                            done += 1
                            if task.cancelled(): continue
                            if task.result() == False: failed[index] = ''
                        elif cancel:
                            if not task.cancelled(): task.cancel()
                    time.sleep(0.5)
                except KeyboardInterrupt:
                    cancel = True
                finally:
                    if not cancel:
                        print_fit('{} {}'.format(
                            'Downloading...' if done != total else 'All tasks done',
                            progress(done, total, True)
                        ), pin = True)
                    else:
                        print_fit('waiting for cancellation... ({})'.format(total - done), pin = True) 

            if cancel: quit()
            print_fit('Success {}, failure {}, total {}'.format(total - len(failed), len(failed), total))

            resources = [resources[index] for index in failed]
            retry += 1

        for resource in resources: print_fit('{} failed'.format(resource['url']))
        print_fit('-' * 30)
    print_fit('Done!')
    return(nickname, uid, newest_bid)


if __name__ == "__main__":
    main()
