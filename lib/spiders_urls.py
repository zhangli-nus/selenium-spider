# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
import config
import time
from lib.db_users import instogramer, db_instogramer
from lib.logger import spider_logger
from lib.db_imgs import db_imgs
from lib.condition_more_than import count_more_than
import random, math

__author__ = 'ZHANGLI'

class spiders_urls(object):
    def __init__(self, intogram_accounts):
        super(spiders_urls, self).__init__()
        self.intogram_accounts = intogram_accounts
        self.db_users = db_instogramer()
        self.logger = spider_logger()
        self.db_imgs = db_imgs()
        pass
    
    def spider_accounts(self):
        self.logger.print_info('start crawl intogram account')
        for base_url in self.intogram_accounts:
            chromeOptions = webdriver.ChromeOptions()
            prefs = {"profile.managed_default_content_settings.images":2}
            chromeOptions.add_experimental_option("prefs",prefs)
            self.driver = webdriver.Chrome(chrome_options=chromeOptions)
            self.process_elements = []
            self.spider_account(base_url)
            self.process_elements = []
            self.driver.close()
            time.sleep(random.randint(30, 90))
            
    def spider_account(self, base_url):
        self.base_url = base_url
        try:
            self.spider_openpage(base_url)
            user = self.spider_crawl_user(base_url)
            self.db_users.update_users(user)
            self.spider_to_bottom(base_url)
        except Exception as e:
            self.logger.print_error('error to crawl user info exception '+ str(e))
    
    def spider_openpage(self, base_url):
        self.driver.get(base_url)
        self.spider_wait_load_all()
    
    def spider_crawl_user(self, base_url):
        user_dict = {}
        element = self.driver.find_element_by_xpath("//h1")
        user_dict['name'] = element.text
        user_dict['base_url'] = base_url
        info = []
        elements = self.driver.find_elements_by_xpath("//span[@class='_bkw5z']")
        for element in elements:
            if element.get_attribute("title"):
                num = element.get_attribute("title")
                info.append(int(self.normalize_num_str(num)))
            else:
                num = element.text
                info.append(int(self.normalize_num_str(num)))
        user_dict['posts'],user_dict['followers'],user_dict['followings'] = info[0], info[1], info[2]
        return instogramer(user_dict)
    
    def spider_to_bottom(self, base_url):
        try:
            js = "window.scrollTo(0,document.body.scrollHeight)"
            self.driver.execute_script(js)
        except Exception as e:
            self.logger.print_error('scroll fail' + str(e))
        try:
            self.spider_click(xpath = "//a[@class='_oidfu']")
        except Exception as e:
            self.logger.print_error('click fail ' + str(e))
        self.spider_scroll_down(base_url)
    
    def spider_click(self, xpath):
        element = self.driver.find_element_by_xpath(xpath)
        element.click()
        self.driver.implicitly_wait(time_to_wait = 3)
    
    def spider_scroll_down(self, base_url):
        unchange_time = 0
        last_process_time = time.time()
        try:
            while True:
                num = self.spider_get_imgs_num()
                print base_url, str(num)
                try:
                    self.logger.print_info("start scroll up")
                    for idx in range(0, random.randint(1,4)):
                        scroll_len = random.randint(-200, -50)* min(math.ceil(math.sqrt(num)/15), 10)
                        js = "window.scrollBy(0, %d)"%(scroll_len+idx)
                        self.driver.execute_script(js)
                        time.sleep(0.1)
                    time.sleep(random.randint(25, 75)/50.0)
                    self.logger.print_info("start scroll down")
                    js = "window.scrollTo(0, document.body.scrollHeight)"
                    self.driver.execute_script(js)
                    time.sleep(random.randint(25, 75)/50.0)
                    self.spider_wait_more_than(num = num)
                    self.logger.print_info("finish scroll")
                except Exception as e:
                    self.logger.print_error('scroll fail ' + str(e))
                
                new_num = self.spider_get_imgs_num()
                if new_num==num and unchange_time%3==0:
                    try:
                        self.logger.print_info("start click")
                        self.spider_click(xpath = "//a[@class='_oidfu']")
                        self.logger.print_info("finish click")
                    except NoSuchElementException:
                        pass
                    except Exception as e:
                        self.logger.print_info("exception load more during crawl " + str(e))
                
                new_num = self.spider_get_imgs_num()
                if new_num == num:
                    unchange_time = unchange_time + 1
                else:
                    unchange_time = 0
                self.logger.print_info("new_number: %d, num: %d, unchange_time: %d"%(new_num, num, unchange_time))
                if time.time()-last_process_time>60*30 and new_num > num: #we save the temporal results every 30 minutes
                    imgs_hrefs = self.spider_get_imgs()
                    self.logger.print_info("start update {num} images from {base_url}".format(num = len(imgs_hrefs), base_url = base_url))
                    self.db_imgs.update_imgs(base_url, imgs_hrefs)
                    last_process_time = time.time()
                    self.logger.print_info("finish update {num} images from {base_url}".format(num = len(imgs_hrefs), base_url = base_url))
                                   
                if unchange_time > 5:
                    break
        except Exception as e: 
            self.logger.print_error("scroll to bottom error " + str(e))
        finally:
            imgs_hrefs = self.spider_get_imgs()
            self.db_imgs.update_imgs(base_url, imgs_hrefs)
        return
    
    def spider_get_imgs(self):
        '''confirm the correspondence of href and src'''
        try:
            imgs_href = []
            start_time = time.time()
            hrefs = self.driver.find_elements_by_xpath("//div[@class='_nljxa']/div[@class='_myci9']/a[@href]")            
            stage1_time = time.time()
            self.logger.print_info("locating all hrefs using %0.3f"%(stage1_time-start_time))
            if self.process_elements: #reduce time
                last_process_idx = self.process_elements[-1]
            else:
                last_process_idx = 0
            for idx, href in enumerate(hrefs[last_process_idx:]):
                img = href.find_element_by_xpath(".//img")
                if img.get_attribute('src'):
                    imgs_href.append((img.get_attribute('src'), href.get_attribute('href')))
                if idx%1001==1000:
                    stage2_time = time.time()
                    self.logger.print_info("locating 1000 hrefs using %0.3f"%(stage2_time-stage1_time))
            self.process_elements.append(len(hrefs))
            stage2_time = time.time()
            self.logger.print_info("locating all img src using %0.3f"%(stage2_time-stage1_time))
        except Exception:
            imgs_href = []
        return imgs_href
    
    def spider_get_imgs_ok(self):
        try:
            start_time = time.time()
            hrefs = self.driver.find_elements_by_xpath("//div[@class='_nljxa']/div[@class='_myci9']/a[@href]")
            stage1_time = time.time()
            self.logger.print_info("locating all hrefs using %0.3f"%(stage1_time-start_time))
            imgs = self.driver.find_elements_by_xpath("//div[@class='_nljxa']/div[@class='_myci9']/a[@href]//img")
            stage2_time = time.time()
            self.logger.print_info("locating all imgs using %0.3f"%(stage2_time-stage1_time))
        except Exception:
            hrefs = imgs = imgs_href = []
        try:
            imgs_href = []
            for (href, img) in zip(hrefs, imgs):
                imgs_href.append((img.get_attribute('src'), href.get_attribute('href')))
            self.logger.print_info("locating all img src using %0.3f"%(time.time()-start_time))
        except Exception:
            imgs_href = []
            self.logger.print_error("differnet img and hrefs length: img num: %d, hrefs: %d"%(len(imgs), len(hrefs)))        
        return imgs_href
    
    def spider_get_imgs_fail(self):
        try:
            start_time = time.time()
            hrefs = self.driver.find_elements_by_xpath("//div[@class='_nljxa']/div[@class='_myci9']/a[@href]")
            stage1_time = time.time()
            self.logger.print_info("locating all hrefs using %0.3f"%(stage1_time-start_time))
            imgs = self.driver.find_elements_by_xpath("//div[@class='_nljxa']/div[@class='_myci9']/a[@href]//img")
            stage2_time = time.time()
            self.logger.print_info("locating all imgs using %0.3f"%(stage2_time-stage1_time))
        except Exception:
            hrefs = imgs = imgs_href = []
        try:
            imgs_href = []
            for (href, img) in zip(hrefs, imgs):
                img_src = self.driver.execute_script("return arguments[0].src;", img)
                href_src = self.driver.execute_script("return arguments[0].href;", href)
                imgs_href.append((img_src, href_src))
            self.logger.print_info("locating all img src using %0.3f"%(time.time()-start_time))
        except Exception:
            self.logger.print_error("differnet img and hrefs length: img num: %d, hrefs: %d"%(len(imgs), len(hrefs)))
            imgs_href = self.spider_get_imgs_slow()   
        return imgs_href
    
    def spider_get_imgs_num(self):
        try:
            hrefs = self.driver.find_elements_by_xpath("//div[@class='_nljxa']/div[@class='_myci9']/a[@href]")
        except Exception:
            return 0
        return len(hrefs)
    
    def spider_wait_load_all(self, implicitly_wait_time = 5):
        self.driver.implicitly_wait(implicitly_wait_time)
        try:
            WebDriverWait(self.driver, config.TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='_nljxa']"))
            )
        except Exception as e:
            self.logger.print_warn('loading timeout exception '+ str(e))
    
    def spider_wait_more_than(self, implicitly_wait_time = 5, num = 0):
        self.driver.implicitly_wait(implicitly_wait_time)
        try:
            WebDriverWait(self.driver, timeout=30).until(
                count_more_than(self.driver, "//div[@class='_nljxa']/div[@class='_myci9']/a[@href]", num)
            )
        except Exception as e:
            self.logger.print_info('loading wait_increase failure ' + str(e))
    
            
    def normalize_num_str(self, num):
        num = num.replace(',','')
        num = num.replace('k', '000')
        num = num.replace('m', '000000')
        return num
        