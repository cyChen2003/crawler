import asyncio
import configparser
import json
import os
import re
import time

import requests
import aiohttp

from utils import XBogusUtil
from utils import Sleep

# 读取配置文件
try:
    config = configparser.RawConfigParser()
    config.read('config.ini')
    con = dict(config.items('douyin'))
    if con is {}:
        raise Exception
    cookie = con.get('cookie')
    if cookie == '':
        raise Exception
except Exception as e:
    exit('请检查当前目录下的config.ini文件配置')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Referer': 'https://www.douyin.com/',
    'Cookie': cookie
}


class CrawlHome(object):
    def __init__(self):
        self.session = requests.Session()
        # 防止开vpn了requests模块报ssl异常
        self.session.trust_env = False
        self.video_info_list = []
        self.picture_info_list = []
        self.author_name = ''
        self.author_info = {}
        self.aweme_id = ''
        self.save_dict = {}
    def analyze_video_input(self, user_in):
        try:
            u = re.search(r'modal_id=(\w+)', user_in)
            if u:
                return u.group(1)
            #如果https://www.douyin.com/video/7142834449816833318?modeFrom=
            u = re.search(r'video/(\w+)', user_in)
            if u:
                return u.group(1)
            u = re.search(r'https://v.douyin.com/(\w+)/', user_in)
            if u:
                url = u.group(0)
                res = self.session.get(url=url, headers=headers).url
                uid = re.search(r'video/(\w+)', res)
                if uid:
                    return uid.group(1)
            return
        except Exception as e:
            return
    def analyze_user_input(self, user_in):
        try:
            u = re.search(r'user/([-\w]+)', user_in)
            if u:
                return u.group(1)
            u = re.search(r'https://v.douyin.com/(\w+)/', user_in)
            if u:
                url = u.group(0)
                res = self.session.get(url=url, headers=headers).url
                uid = re.search(r'user/([-\w]+)', res)
                if uid:
                    return uid.group(1)

        except Exception as e:
            return
    def get_video_info(self, user_in, sleep=False):
        sec_uid = self.analyze_user_input(user_in)
        modal_id = self.analyze_video_input(user_in)
        self.get_video_url(modal_id)
        # self.get_author_info(sec_uid)
        self.get_comment(modal_id)

    def get_video_url(self, modal_id):
        self.save_dict['aweme_id'] = modal_id
        url = f'https://www.douyin.com/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&channel=channel_pc_web&aweme_id={modal_id}&&cookie_enabled=true&platform=PC'
        xbs = XBogusUtil.generate_url_with_xbs(url, headers.get('User-Agent'))
        url = url + '&X-Bogus=' + xbs
        json_str = self.session.get(url, headers=headers).json()
        self.author_name = json_str['aweme_detail']['author']['nickname']
        self.author_info['author_name'] = self.author_name
        if json_str['aweme_detail']['author']['signature'] is not None:
            self.author_info['signature'] = json_str['aweme_detail']['author']['signature']
        else:
            self.author_info['signature'] = '无'
        if json_str['aweme_detail']['author']['total_favorited'] is not None:
            self.author_info['total_favorited'] = json_str['aweme_detail']['author']['total_favorited']
        else:
            self.author_info['total_favorited'] = 0
        if json_str['aweme_detail']['video']['play_addr']['url_list'] is not None:

            self.save_dict['video_desc'] = json_str['aweme_detail']['desc']
            self.save_dict['ocr_content'] = json_str['aweme_detail']["seo_info"]["ocr_content"]
            self.save_dict['keywords'] = json_str['aweme_detail']['caption']
            url = json_str['aweme_detail']['video']['play_addr']['url_list'][0]
            self.video_info_list.append({'video_desc': json_str['aweme_detail']['desc'], 'video_url': url,'aweme_id':modal_id})
        self.save_dict['author_info'] = self.author_info
    # 默认开启睡眠
    def get_home_video(self, user_in, sleep=False):
        sec_uid = self.analyze_user_input(user_in)
        cursor = 0
        if sec_uid is None:
            exit("粘贴的用户主页地址格式错误")
        home_url = f'https://www.douyin.com/aweme/v1/web/aweme/post/?aid=6383&sec_user_id={sec_uid}&count=35&max_cursor={cursor}&cookie_enabled=true&platform=PC&downlink=10'

        xbs = XBogusUtil.generate_url_with_xbs(home_url, headers.get('User-Agent'))
        url = home_url + '&X-Bogus=' + xbs
        json_str_user = self.session.get(url, headers=headers).json()
        # print(json_str)

        self.author_name = json_str_user['aweme_list'][0]['author']['nickname']  # 获取作者名称
        self.author_info['author_name'] = self.author_name
        self.get_author_info(sec_uid)

        while 1:
            home_url = f'https://www.douyin.com/aweme/v1/web/aweme/post/?aid=6383&sec_user_id={sec_uid}&count=35&max_cursor={cursor}&cookie_enabled=true&platform=PC&downlink=10'
            xbs = XBogusUtil.generate_url_with_xbs(home_url, headers.get('User-Agent'))
            url = home_url + '&X-Bogus=' + xbs
            json_str = self.session.get(url, headers=headers).json()
            #如果没有has_more字段，说明请求失败，退出
            if 'has_more' not in json_str:
                break
            cursor = json_str["max_cursor"]  # 当页页码
            for i1 in json_str["aweme_list"]:
                #  视频收集
                if i1["images"] is None:
                    aweme_id = i1["aweme_id"]
                    self.get_comment(aweme_id)
                    name = i1["desc"]
                    url = i1["video"]["play_addr"]["url_list"][0]
                    # url = i1["video"]['bit_rate'][0]['play_addr']['url_list'][0]
                    self.video_info_list.append({'video_desc': name, 'video_url': url,'aweme_id':i1['aweme_id']})
                #  图片收集
                else:
                    self.picture_info_list += list(map(lambda x: x["url_list"][-1], i1["images"]))

            if json_str["has_more"] == 0:
                break

            # 随机睡眠
            if sleep:
                Sleep.random_sleep()
    def get_comment(self, aweme_id):

        comments_url = f'https://www.douyin.com/aweme/v1/web/comment/list/?device_platform=webapp&aid=6383&channel=channel_pc_web&aweme_id={aweme_id}&cookie_enabled=true&platform=PC&downlink=10&cursor=0&count=20'
        xbs = XBogusUtil.generate_url_with_xbs(comments_url, headers.get('User-Agent'))
        comments_url = comments_url + '&X-Bogus=' + xbs
        comments_json = self.session.get(comments_url, headers=headers).json()
        self.save_dict['comments'] = []
        if 'comments' in comments_json and comments_json['comments'] is not None:
            for comment in comments_json['comments']:
                self.save_dict['comments'].append((comment['text'], comment['digg_count']))

    def get_author_info(self, sec_uid):
        user_info_url = f'https://www.douyin.com/aweme/v1/web/user/profile/other/?device_platform=webapp&aid=6383&channel=channel_pc_web&publish_video_strategy_type=2&source=channel_pc_web&sec_user_id={sec_uid}&cookie_enabled=true&platform=PC'
        xbs = XBogusUtil.generate_url_with_xbs(user_info_url, headers.get('User-Agent'))
        user_info_url = user_info_url + '&X-Bogus=' + xbs
        json_str_user_info = self.session.get(user_info_url, headers=headers).json()
        if json_str_user_info['user'] is not None:
            if json_str_user_info['user']['signature'] is not None:
                self.author_info['signature'] = json_str_user_info['user']['signature']
            else:
                self.author_info['signature'] = '无'
            if json_str_user_info['user']['total_favorited'] is not None:
                self.author_info['total_favorited'] = json_str_user_info['user']['total_favorited']
        #将author信息保存到save_dict
        self.save_dict['author_info'] = self.author_info
async def save_to_disk(c):
    #save_to_disk(video_list, picture_list):
    video_list = c.video_info_list
    picture_list = c.picture_info_list
    count = 1
    tasks = []
    # 协程限制5个并发
    # semaphore = asyncio.Semaphore(5)
    async with aiohttp.ClientSession(headers=headers) as session:
        for i in video_list:
            url = i.get('video_url')
            aweme_id = i.get('aweme_id')
            c.aweme_id = aweme_id
            # async with semaphore:
            task = asyncio.ensure_future(download_video(session, aweme_id, url))
            tasks.append(task)
            count += 1
        for i in picture_list:
            # async with semaphore:
            task = asyncio.ensure_future(download_pic(session, count, i))
            tasks.append(task)
            count += 1
        await asyncio.gather(*tasks)


async def download_video(session, filename, url):
    # await asyncio.sleep(0.5)
    try:
        async with session.get(url) as response:
            if response.status == 200:
                with open(f'{filename}.mp4', "wb") as f:
                    async for chunk in response.content.iter_chunked(1024):
                        f.write(chunk)
    except Exception as ex:
        print(ex)


async def download_pic(session, filename, url):
    # await asyncio.sleep(0.3)
    try:
        async with session.get(url) as response:
            if response.status == 200:
                with open(f'{filename}.jpg', "wb") as f:
                    async for chunk in response.content.iter_chunked(1024):
                        f.write(chunk)
    except Exception as ex:
        print(ex)


def download_main(c):
    # download_main(c.author_name, c.video_info_list, c.picture_info_list)
    author_name = c.author_name
    video_list = c.video_info_list
    picture_list = c.picture_info_list
    if not os.path.exists(author_name):
        os.mkdir(author_name)
    os.chdir(author_name)
    # loop = asyncio.get_event_loop()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(save_to_disk(c))
    os.chdir("..")
    save_dir = os.path.join(os.getcwd(), author_name)
    # with open(f'{save_dir}/author.json', 'w', encoding='utf-8') as f:
    #     f.write(str(c.author_info))
    #保存author信息
    json.dump(c.author_info, open(f'{save_dir}/author.json', 'w', encoding='utf-8'), ensure_ascii=False)

    #保存aweme_id信息
    json.dump(c.save_dict, open(f'{save_dir}/{c.aweme_id}.json', 'w', encoding='utf-8'), ensure_ascii=False)

# def download_

if __name__ == '__main__':
    c = CrawlHome()
    user_in = "https://www.douyin.com/video/7366934119026036031?modeFrom="
    print('开始解析请等待...')
    start_time = time.time()
    # c.get_home_video(user_in)
    # print('共解析到' + str(len(c.video_info_list)) + '个视频,' + str(len(c.picture_info_list)) + '张图片')
    # print('开始下载,请稍等...')
    # download_main(c.author_name, c.video_info_list, c.picture_info_list)
    # end_time = time.time()
    # cost_time = format(end_time - start_time, '.2f')
    # print('下次完成，共花费时间' + cost_time + 's')
    c.get_video_info(user_in)
    download_main(c)
