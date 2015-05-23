#!/usr/local/bin/python2.7

import gevent.monkey
gevent.monkey.patch_socket()
gevent.monkey.patch_ssl()
from gevent.pool import Pool
import requests
import itertools
import time
import sys

#-- Request headers
base_url = 'https://api.happn.fr/api/'
oauth_key = 'xxx'
headers = {
    'Host': 'api.happn.fr',
    'Accept': '*/*',
    #'Proxy-Connection': 'close',
    'Authorization': 'OAuth="%s"' % oauth_key,
    'Accept-Language': 'en-US;q=1,en;q=0.75',
    'Accept-Encoding': 'gzip, deflate',
    #'Signature': '7790f4c318d5e89c6a5cf072e8992xxxxxxxxxxxxxxxx78da93ae6f80b76a817', #randomize
    'User-Agent': 'happn/820 CFNetwork/711.1.16 Darwin/14.0.0',
    #'Connection': 'close'
    #'Cookie': 'PHPSESSID=xxxxxxxxxxa3tndm1uplh030adncqun5'
}
put_headers = headers.copy()
put_headers['Content-Type'] = 'application/x-www-form-urlencoded'

lim = 50
if len(sys.argv) == 3:
    off = int(sys.argv[1])
    maxlim = int(sys.argv[2])
    do_change = False
else:
    off = 0
    maxlim = 200
    do_change = True

#-- Where you at, bro? --#
spacing = 100
lat_start, lat_end = (407100, 407301)  #(407000, 407480)
long_start, long_end = (-740000, -739791)  #(-740130, -739720)
#------------------------#

pos_wait = 60 * 22  #22 minutes for loc update
pos_wait_fail = 60 * 2  #in case im wrong about the 25

pos_url = base_url + 'users/me/position'
notif_url = base_url + """users/me/notifications?fields=notifier.fields(id%5C,picture%5C.fields%5C(url%5C)%5C.width%5C(290%5C)%5C.mode%5C(0%5C)%5C.height%5C(500%5C)%5C,first_name%5C,my_relation%5C.fields%5C(id%5C))&types=468"""
#notification_type,creation_date,nb_times,modification_date,notifier.fields(id%5C,age%5C,school%5C,workplace%5C,last_meet_position%5C,picture%5C.fields%5C(url%5C%5C%5C,id%5C%5C%5C,is_default%5C)%5C.width%5C(290%5C)%5C.mode%5C(0%5C)%5C.height%5C(500%5C)%5C,is_accepted%5C,first_name%5C,fb_id%5C,my_relation%5C.fields%5C(id%5C)%5C,is_charmed%5C.fields%5C(id%5C)%5C,distance%5C,job%5C,nb_photos%5C,gender%5C,about%5C,modification_date%5C,profiles%5C.width%5C(640%5C)%5C.mode%5C(1%5C)%5C.height%5C(1136%5C))

def fetch(pid):
    accept_url = base_url + 'users/me/accepted/%s' % pid
    r = requests.request('POST', accept_url, headers=put_headers, data={'id': pid})
    
    try:
        like_json = r.json()
    except:
        print 'Error making request to %s' % r.url
    else:
        if not like_json.get('success'):
            print 'Error from app liking %s' % r.url
            print like_json
        else:
            print 'Liked successfully: %s' % accept_url
            
    r.close()
    return

def like_all():
    more = True
    fetched = 0
    offset = off
    limit = lim
    while more:
        if (fetched < maxlim) or (maxlim == 0):
            if (maxlim > 0):
                limit = min(limit, maxlim - fetched)
            offset_url = notif_url + '&limit=%s&offset=%s' % (limit, offset)
            print 'requesting offset %s' % offset
            resp = requests.get(offset_url, headers=headers)
            
            if resp.status_code != 200:
                print 'error code %s' % resp.status_code
            else:
                pid_list = []
                resp_json = resp.json()
                data = resp_json.get('data')
                if not data:
                    more = False
                else:
                    #dump data into file
                    for d in data:
                        notif = d.get('notifier', {})
                        #get last check date. any modification_date on d older can
                        #more = False
                        #break
                        person_id = notif.get('id')
                        person_name = notif.get('first_name')
                        person_picture = notif.get('picture', {}).get('url')
                        if notif.get('my_relation') == 0:
                            print 'LIKING:    %s (%s)\t%s' % (person_name, person_id, person_picture)
                            pid_list.append(person_id)
                        else:
                            print 'Skipping:  %s (%s)\t%s' % (person_name, person_id, person_picture)
                    
                    if pid_list:
                        pool = Pool()
                        for p in pid_list:
                            pool.spawn(fetch, p)
                        pool.join()
                    
                    offset += limit
                    fetched += limit
            
            time.sleep(0.5)
        
        else:
            more = False
    
    return

def change_pos(pos, check):
    pos_data = {
        'latitude': pos[0],
        'longitude': pos[1]
    }
    print 'Attempting to change position...'
    result = requests.post(pos_url, headers=put_headers, data=pos_data)
    
    if result.status_code != 200:
        print 'pos change didnt work (%s), trying again in %s sec' % (result.status_code, pos_wait_fail)
        print result.text
        result.close()
        check += 1
        if check < 20:
            time.sleep(pos_wait_fail)
            return change_pos(pos, check)
        else:
            print 'too many checks'
            sys.exit(1)
    else:
        result_json = result.json()
        if result_json.get('success'):
            print 'CHANGED position to %s,%s' % pos
            #start liking people
            like_all()
            print 'sleeping for %s sec for next pos change' % pos_wait
            time.sleep(pos_wait)
        else:
            print 'something bad happened'
            print result_json
            sys.exit(1)

if do_change:
    """
    lats = range(lat_start, lat_end, spacing)
    longs = range(long_start, long_end, spacing)
    sublats = [la+(spacing/2) for la in lats][:-1]
    sublongs = [lo+(spacing/2) for lo in longs][:-1]

    positions = []
    for lat,long in itertools.product(lats, longs):
        positions.append(('{0:.6f}'.format(lat/10000.0), '{0:.6f}'.format(long/10000.0)))
    for lat,long in itertools.product(sublats, sublongs):
        positions.append(('{0:.6f}'.format(lat/10000.0), '{0:.6f}'.format(long/10000.0)))
    """
    
    #positions = [(40.729535,-73.996739),(40.737713,-73.996610),(40.751889,-73.993499),(40.755449,-73.987276),(40.750947,-73.976397),(40.757302,-73.970561),(40.772823,-73.982276),(40.769824,-73.972588),(40.808336,-73.961699),(40.733827,-73.987298),(40.731193,-73.978285)]
    positions = [(40.743000,-73.987500), (40.722000,-74.000000), (40.722000,-73.990000), (40.722000,-73.980000), (40.736000,-74.000000), (40.736000,-73.990000), (40.736000,-73.980000), (40.750000,-74.000000), (40.750000,-73.990000), (40.750000,-73.980000), (40.704261,-74.012510), (40.707254,-74.007446), (40.713646,-74.009785), (40.742867,-73.980431), (40.717500,-74.005000), (40.715000,-73.995000), (40.715000,-73.985000), (40.729000,-74.005000), (40.729000,-73.995000), (40.729000,-73.985000)]
    
    #-- Submit my positions
    #while keep_changing:
    for pos in positions:
        change_pos(pos, 0)
else:
    #-- Get the possible matches
    like_all()
