#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Created on Sep 21, 2013 5:13:22 PM

# ***************************************************************************
# *   Copyright (C) 2013, Paul Lutus                                        *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License as published by  *
# *   the Free Software Foundation; either version 2 of the License, or     *
# *   (at your option) any later version.                                   *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU General Public License for more details.                          *
# *                                                                         *
# *   You should have received a copy of the GNU General Public License     *
# *   along with this program; if not, write to the                         *
# *   Free Software Foundation, Inc.,                                       *
# *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.             *
# ***************************************************************************

# requires use of ClipboardAssistant or SSHelper on Android device

# https://play.google.com/store/apps/details?id=com.rs.clipboardassistant&hl=en
# https://play.google.com/store/apps/details?id=com.arachnoid.sshelper&hl=en

VERSION = '1.4'

import sys,os,re

import zipfile, getpass,urllib2,MySQLdb, time, json, platform, random

from optparse import OptionParser

import LibraryDBGUI

import wx,gettext

# suppress MySQL warnings

#import warnings 
#warnings.simplefilter("ignore")

# see wx.tools.img2py

from wx.lib.embeddedimage import PyEmbeddedImage

# a 32x32 PNG with transparency

class Icon:
  book_red_icon32x32 = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAMAAABEpIrGAAAAM1BMVEU4AAAeEQlQIAVcJQJo"
    "LQV0NAKBNwV4PAlZRTR1RCGRUh+pdUiRfGW9nXnbv2Pdx6Tx4sQWq65OAAAAAXRSTlMAQObY"
    "ZgAAAAFiS0dEAIgFHUgAAAAJcEhZcwAACxMAAAsTAQCanBgAAAAHdElNRQfdCRwPOQUAGREP"
    "AAABAklEQVQ4y82TWY7EIAxEE7sMDYkH3/+0YxOy9UT92RpHIks9V1mCTNPXSyCS8wc993Ls"
    "mYJr7iC5OgU49qdfJKUkUehW935EfwDYq7zpQIoCeOj6pI9+z0DTNz2Ivdvf1cpVZzCHOfst"
    "LhRTPvRNDZGPCVs7dWAIAfQhMl8CuPvuFg7E42IL33XwYeSLWLvpYOomY8UlICSRLWMQBPKA"
    "fYAXUf/sCHltZLZ2bMPaVmfgWEe2rGbnPq5mLRhGtwoT0jNgmkhVndH1VSB9Rqqm6bJLcyna"
    "ooLJ4g5m6XYOfuaZ6skszerDaZt5GYya1ucTS9iYt4CbDeVFrX78MWbk6b/VLzDvC33kXvXt"
    "AAAAAElFTkSuQmCC")


class LibraryDB:
  
  def write_file(self,path,data):
    with open(path,'w') as f:
      f.write(data)
      
  def read_file(self,path):
    with open(path) as f:
      return f.read()  

  def __init__(self):
    
    # these may be redefined by the user
    # before the program is first run
  
    self.db_name = u'books' 
    self.table_name = u'isbnwc_books'
    
    self.help_url = 'http://arachnoid.com/LibraryDB'
    self.gui = False
    self.pw = False
    self.create = False
    self.rebuild_tbl = False
    self.verbose = False
    self.timer = False
    self.timer2 = False
    
    self.db_conn = False
    self.url_server = ''
    self.pw_server = ''
    self._url_mode = False
    self._url_running = False
    
    self.class_name = self.__class__.__name__
    
    self.ini_filename = self.class_name + '.ini'
  
    # URL for online database
  
    self.baseurl = 'http://xisbn.worldcat.org/webservices/xid/isbn/%s?method=getMetadata&format=json&fl=*'
  
    self.path = os.getcwd()
  
    # local data directories
  
    self.isbnsrc = self.path + "/isbn_scanned_codes"
  
    self.isbndest = self.path + '/isbnwc_retrieved_json'
    
    self.platform_windows = re.search('(?i)windows',platform.system()) != None
    
    shells = {
  "speak.sh" :
    """
      #!/bin/sh
      echo "$@" | festival --tts
    """,
  "speak.vbs" :
    """
      set s = CreateObject("SAPI.SpVoice")
      s.Speak Wscript.Arguments(0), 3
      s.WaitUntilDone(3000)
    """
    }
    
    # export shells for voice synthesis if needed
    
    key = ('speak.sh','speak.vbs')[self.platform_windows]
    
    if(not os.path.exists(key)):
      self.write_file(key,shells[key])
    if(not self.platform_windows):
      os.system('chmod +x %s' % key)
  
    # create directories as needed
  
    for path in [self.isbnsrc,self.isbndest]:
      if(not os.path.exists(path)):
        os.makedirs(path)
  
    self.new_db_recs = 0
    self.duplicate_db_recs = 0
    self.new_online_queries = 0
    self.data_errors = 0
    self.isbn_errors = 0
  
    self.announce = False
  
    if('USER' in os.environ):
      self.user_name = os.environ['USER']
    elif('USERNAME' in os.environ):
      self.user_name = os.environ['USERNAME']
    else:
      self.user_name = 'undefined_user'
      
    self.server_name = 'localhost'
    
      # MySQL instructions to create tables and views
  
    self.sqlsetup = """
    CREATE DATABASE IF NOT EXISTS `%s`;
    use `%s`;
    CREATE TABLE IF NOT EXISTS `%s` (
    Title text not null,
    Author text,
    Publisher text,
    City text,
    Lang text,
    Edition text,
    Year text,
    OCLCN text,
    Url text,
    Form text,
    LCCN text,
    Location text,
    ISBN varchar(32) primary key default '(enter ISBN 13)',
    LastModified timestamp default CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP
    )ENGINE=InnoDB DEFAULT CHARSET=utf8;
    create or replace view %s_sorted_by_title
    as select * from `%s` order by Title;
    create or replace view %s_sorted_by_author
    as select * from `%s` order by Author;
    create or replace view %s_sorted_by_last_modified
    as select * from `%s` order by LastModified;
    """
    
    self.field_names = [
      ['Title','title'],
      ['Author','author'],
      ['Publisher','publisher'],
      ['City','city'],
      ['Language','lang'],
      ['Edition','ed'],
      ['Year','year'],
      ['OCLC','oclcnum'],
      ['Url','url'],
      ['Form','form'],
      ['LCCN','lccn'],
      ['Location','location'],
      ['ISBN','isbn']
    ]
    
    if(len(sys.argv) > 1):
      self.process_comline()
    else:
      self.gui = True
      self.process_gui()
      
  def process_comline(self):
    # user wants a command-line app
    
      self.parser = OptionParser()
      
      self.parser.add_option(
        "-a", "--announce",
        action="store_true",
        dest="announce",
        help="Announce received ISBNs by voice"
        )
      self.parser.add_option(
        "-c", "--create",
        action="store_true",
        dest="create",
        help="Create database and/or table"
        )
      self.parser.add_option(
        "-g", "--gui",
        action="store_true",
        dest="gui",
        help="Use graphical user interface"
        )
      self.parser.add_option(
        "-p", "--password",
        action="store",
        dest="password",
        help="Enter MySQL password"
        )
      self.parser.add_option(
        "-r", "--rebuild",
        action="store_true",
        dest="rebuild_table",
        help="Rebuild table `%s`.`%s` with preserved JSON records"
        % (self.db_name,self.table_name)
        )
      self.parser.add_option(
        "-s", "--server",
        action="store",
        dest="server",
        help='Enter MySQL server name (default "%s")'
        % self.server_name
        )
      self.parser.add_option(
        "-u", "--user",
        action="store",
        dest="user",
        help='Enter MySQL user name (default "%s")'
        % self.user_name
        )
      
      self.parser.add_option(
        "-v", "--verbose",
        action="store_true",
        dest="verbose",
        help="Include extra information"
        )
        
      self.parser.add_option(
        "-x", "--urlurl",
        action="store",
        dest="url_server",
        help="Server URL"
        )
      
      self.parser.add_option(
        "-y", "--usurl",
        action="store",
        dest="user_server",
        help="Server user"
        )
        
      self.parser.add_option(
        "-z", "--pwurl",
        action="store",
        dest="pw_server",
        help="Server password"
        )
      
      (self.options,args) = self.parser.parse_args()
      
      if(self.options.announce):
        self.announce = True
        
      if(self.options.create):
        self.create = True
        
      if(self.options.gui):
        self.gui = True
        
      if(self.options.rebuild_table):
        self.rebuild_tbl = True
        
      if(self.options.verbose):
        self.verbose = True
        
      if(self.options.server):
        self.server_name = self.options.server
        
      if(self.options.user):
        self.user_name = self.options.user
      
      if(self.options.url_server):
        self.url_server = self.options.url_server
        self._url_mode = True
        
      if(self.options.user_server):
        self.user_server = self.options.user_server

      if(self.options.pw_server):
        self.pw_server = self.options.pw_server
        
      if(self.options.password):
        self.pw = self.options.password
        
      self.process_console()
    
  def process_gui(self):
    gettext.install("app") # replace with the appropriate catalog name
    app = wx.PySimpleApp(0)
    wx.InitAllImageHandlers()
    self.gui_frame = LibraryDBGUI.LibraryDBGUI(None, wx.ID_ANY, "" )
    self.gui_frame.SetTitle(self.class_name + ' ' + VERSION)
    self.gui_frame.SetIcon(Icon.book_red_icon32x32.GetIcon())
    app.SetTopWindow(self.gui_frame)
    self.gui_frame.Show()
    self.gui_frame.Bind(wx.EVT_CLOSE,self.gui_exit)
    for b in (
      self.gui_frame.create_table_button,
      self.gui_frame.rebuild_table_button,
      self.gui_frame.start_button,
      self.gui_frame.stop_button,
      self.gui_frame.erase_log_button,
      self.gui_frame.help_button,
      self.gui_frame.quit_button
    ):
      b.Bind(wx.EVT_BUTTON,self.button_press)
    for cb in (
      self.gui_frame.chkbox_verbose,
      self.gui_frame.chkbox_voice,
      self.gui_frame.radio_parse,
      self.gui_frame.radio_url,
      self.gui_frame.chkbox_save_passwords,
    ):
      cb.Bind(wx.EVT_CHECKBOX,self.update_control_vals)
      cb.Bind(wx.EVT_RADIOBUTTON,self.update_control_vals)
    self.read_config()
    app.MainLoop()
  
  def gui_exit(self,x = False):
    self.write_config()
    self.gui_frame.Destroy()
    
  def button_press(self,x):
    if(self.db_conn):
      self.db_conn.commit()
      self.db_conn.close()
      self.db_conn = False
    self._url_running = False
    self.update_control_vals()
    self.reset_values()
    self.gui_frame.notebook1.SetSelection(1)
    b = x.GetEventObject()
    if(b == self.gui_frame.create_table_button):
      result = self.create_db_table(self.db_name,self.table_name)
    if(b == self.gui_frame.rebuild_table_button):
      self.rebuild_table()
    elif(b == self.gui_frame.start_button):
      self.core_process()
    elif(b == self.gui_frame.stop_button):
      self._url_running = False
    elif(b == self.gui_frame.help_button):
      self.log('Launching browser for %s\n' % self.help_url)
      wx.LaunchDefaultBrowser(self.help_url)
    elif(b == self.gui_frame.erase_log_button):
      self.gui_frame.txt_log.SetValue('')
    elif(b == self.gui_frame.quit_button):
      self.gui_exit()
  
  # these two functions get/set the GUI frame size
  
  def GetValue(self):
    w,h = self.gui_frame.GetSize()
    return '%d,%d' % (w,h)
    
  def SetValue(self,s):
    self.gui_frame.SetSize([int(x) for x in s.split(',')])
    
  def read_config(self):
    self.config_keys = {
      'mysql_server' : self.gui_frame.txt_mysql_server,
      'mysql_user' : self.gui_frame.txt_mysql_user,
      'mysql_password' : self.gui_frame.txt_mysql_password,
      'mysql_db_name' : self.gui_frame.txt_mysql_database,
      'mysql_table_name' : self.gui_frame.txt_mysql_table,
      'url_server' : self.gui_frame.txt_url_server,
      'url_user' : self.gui_frame.txt_url_user,
      'url_password' : self.gui_frame.txt_url_password,
      'url_mode' : self.gui_frame.radio_url,
      'file_parse_mode' : self.gui_frame.radio_parse,
      'voice_prompts' : self.gui_frame.chkbox_voice,
      'verbose' : self.gui_frame.chkbox_verbose,
      'save_passwords' : self.gui_frame.chkbox_save_passwords,
      'display_size' : self
      }
    self.config_vals = {
      'mysql_server' : 'localhost',
      'mysql_user' : self.user_name,
      'mysql_password' :  'xxxxxx',
      'mysql_db_name' : self.db_name,
      'mysql_table_name' : self.table_name,
      'url_server' : 'name/IP:port',
      'url_user' : '(not used in this version)',
      'url_password' : '',
      'url_mode' : 'False',
      'file_parse_mode' : 'True',
      'voice_prompts' : 'False',
      'verbose' : 'False',
      'save_passwords' : 'False',
      'display_size' : '740,320'
      }
    
    if(os.path.exists(self.ini_filename)):
      data = self.read_file(self.ini_filename)
      data = data.strip()
      for line in re.split('\n+',data):
        s = re.split(' = ',line)
        if(len(s) == 2):
          self.config_vals[s[0]] = s[1].strip()
      
    for key in self.config_keys.keys():
      comp = self.config_keys[key]
      if(isinstance(comp,wx.CheckBox) or isinstance(comp,wx.RadioButton)):
        comp.SetValue(self.config_vals[key] == 'True')
      elif(isinstance(comp,wx.TextCtrl)):
        comp.SetValue(self.config_vals[key])
      elif(isinstance(comp,LibraryDB)):
        comp.SetValue(self.config_vals[key])
      else:
        self.log('Unrecognized control: %s\n' % str(comp))
    self.update_control_vals()
      
  def write_config(self):
    self.update_control_vals()
    config = ''
    for key in sorted(self.config_keys.keys()):
      comp = self.config_keys[key]
      if(self.save_passwords or not (isinstance(comp,wx.TextCtrl) and comp.GetWindowStyle() == wx.TE_PASSWORD)):
        s = '%s = %s\n' % (key, self.config_vals[key])
        config += s
    self.write_file(self.ini_filename,config)
  
  def update_control_vals(self,x=False):
    for key in sorted(self.config_keys.keys()):
      self.config_vals[key] = self.config_keys[key].GetValue()
    self.pw = self.config_vals['mysql_password']
    self.user_name = self.config_vals['mysql_user']
    self.db_name = self.config_vals['mysql_db_name']
    self.table_name = self.config_vals['mysql_table_name']
    self.url_server = self.config_vals['url_server']
    self.pw_server = self.config_vals['url_password']
    self.us_url = self.config_vals['url_user']
    self._url_mode = str(self.config_vals['url_mode']) == 'True'
    self.announce = str(self.config_vals['voice_prompts']) == 'True'
    self.verbose = str(self.config_vals['verbose']) == 'True'
    self.save_passwords = str(self.config_vals['save_passwords']) == 'True'
  
  def log(self,s):
    # prevent excessive storage
    if(self.gui):
      out = self.gui_frame.txt_log.GetValue()
      self.gui_frame.txt_log.SetValue(out[-16384:])
      self.gui_frame.txt_log.AppendText(s)
    else:
      sys.stdout.write(s)
    
  def quit_prompt(self):
    raw_input('Press Enter to quit: ')
    quit()
  
  # create connection to MySQL server
  def mysql_connect(self):
    if(self.db_conn):
      return True
    else:
      try:
        self.db_conn = MySQLdb.connect(
          host=self.server_name,
          user=self.user_name,
          passwd=self.pw,
          use_unicode=True,
          charset = 'utf8'
        )
        return True
      except Exception as e:
        if(self.verbose):
          self.log('Error connecting to MySQL server: %s\n' % str(e))
        else:
          self.log('No MySQL server connection.\n')
        self.db_conn = False
        return False
  
  # submit record to MySQL database
  
  def execsql(self,mysql,commit):
    if(not self.db_conn):
      self.mysql_connect()
    result = False
    if(self.db_conn):
      try:
        cursor = self.db_conn.cursor()
        cursor.execute(mysql)
        result = cursor.fetchall()
        cursor.close()
        if(commit):
          self.db_conn.commit()
        self.new_db_recs += 1
        return result
      except Exception as e:
        if(re.search('(?i)duplicate entry',str(e))):
          self.duplicate_db_recs += 1
          return result
        else:
          if(self.verbose):
            self.log('MySQL error: %s\n' % str(e))
          else:
            self.log('MySQL access error.\n')
          return result
  
  # access Web ISBN database
  
  def fetch_web_content(self,url):
    response = False
    try:
      req = urllib2.urlopen(url)
      response = req.read()
    except:
      None
    return response
  
  def get_value(self,js,key):
    if(key == 'location'):
      v = 'h'
    elif(('list' in js) and key in js['list'][0]):
      v = js['list'][0][key]
    else:
      v = ''
    if(type(v) == list):
      s = ','.join(v)
      v = re.sub('"','',s)
    return v
    
  # build and insert a MySQL table record
  
  def create_table_record(self,data,isbn,commit):
    if(not re.search('(?i)isbn',data)):
      self.log('Malformed data source for ISBN %s\n' % isbn)
      self.data_errors += 1
    else:
      js = json.loads(data) 
      fields = []
      for s in self.field_names:
        fn,key = s
        fields.append('"' + self.get_value(js,key) + '"')
      fields.append('NULL') # for last modified
      record = ','.join(fields)
      com = 'INSERT INTO `%s`.`%s` VALUES (%s)' % (self.db_name,self.table_name,record)
      result = self.execsql(com,commit)
      if(result):
        self.log('New database entry for ISBN %s\n' % isbn)
        return True
      else:
        return False
    
  # check preserved XML files for data
  
  def retrieve_existing(self,isbn):
    result = False
    dirlist = os.listdir(self.isbndest)
    for fn in dirlist:
      if(re.search(isbn,fn)):
        result = self.read_file(self.isbndest + '/' + fn)
        break
    return result
  
  def checksum13(self,ss):
    # see http://www.nationallibrary.fi/publishers/isbn/revision.html
    if(len(ss) != 13):
      self.log('Error: ISBN %s not 13 digits.\n' % sn)
      return False
    else:
      sn = ss[0:12]
      # compute checksum
      cs = 0
      for n,s in enumerate(sn):
        cs += int(s) * (1+(n % 2)*2)
      cs = (10-(cs % 10)) % 10
      return int(ss[12]) == cs
  
  def convert13(self,ss):
    # see http://www.nationallibrary.fi/publishers/isbn/revision.html
    n13 = True
    if(len(ss) == 10):
      # convert to interim '978' + n form
      sn = '978' + ss[0:9]
      n13 = False
    elif(len(ss) == 13):
      sn = ss[0:12]
    else:
      self.log('Error: ISBN %s neither 10 nor 13 digits.\n' % ss)
      return False
    # compute checksum
    cs = 0
    for n,s in enumerate(sn):
      cs += int(s) * (1+(n % 2)*2)
    cs = str((10-(cs % 10)) % 10)
    if(n13 and (cs != ss[12])):
      self.log('Error: ISBN %s failed checksum.\n' % ss)
      return False
    return sn + cs
      
  # process ISBN values and acquire records
  
  def process_isbn(self,data,commit):
    data = data.strip()
    records = re.split('\n',data)
    for record in records:
      fields = re.split(',',record)
      isbn = fields[0].strip()
      isbn = re.sub('[^\d\w]','',isbn)
      isbn = self.convert13(isbn)
      if(not isbn):
        self.isbn_errors += 1
        self.error_isbn_codes.append(record)
        if(self._url_running):
          self.voice_announce('Code not valid.')
      else:
        if(self.verbose):
          self.log('ISBN code "%s" accepted.\n' % isbn)
        if(self._url_running):
          self.voice_announce('Code accepted.')
        if(len(fields) < 2):
          self.user_entries.append(isbn)
        data = self.retrieve_existing(isbn)
        if(not data):
          url = self.baseurl % isbn
          if(self.verbose):
            self.log('Web retrieval for ISBN %s\n' % isbn)
          data = self.fetch_web_content(url)
          if(re.search('title',data)):
            self.write_file(self.isbndest + '/' + isbn + '.json',data)
            self.new_online_queries += 1
          else:
            if(self.verbose):
              self.log('Online search failed for ISBN "%s"\n' % isbn)
            self.data_errors += 1
            data = False
        rec = {}
        if(data):
          self.create_table_record(data,isbn,commit)
        else:
          if(self.verbose):
            self.log('No data for ISBN "%s"\n' % isbn)
          self.data_errors += 1
  
  # list ISBN values and resolution
  
  def list_verbose(self,prompt,data):
    if(len(data) > 0):
      ss = []
      for rec in sorted(data):
        p = self.isbndest + '/' + rec + '.json'
        if(not os.path.exists(p)):
          ss.append('  %13s' % rec)
      if(len(ss) > 0):
        self.log('%s unresolved ISBN values:\n' % prompt)
        self.log('%s\n' % '\n'.join(ss))
  
  # create database, table and views if needed, but avoid
  # database lock by trying to create table that exists
  
  def create_db_table(self,db_name,table_name):
    self.log('Creating table `%s`.`%s` if needed ...\n' % (self.db_name,self.table_name))
    result = self.execsql('show tables in `%s` like \'%s\'' % (self.db_name,self.table_name),True)
    if(not result and self.db_conn):
      coms = self.sqlsetup % \
      (self.db_name,self.db_name,self.table_name,
      self.table_name,self.table_name,self.table_name,
      self.table_name,self.table_name,self.table_name
     )
      for com in re.split(';',coms):
        com = com.strip()
        com = re.sub('\n+',' ',com)
        if(len(com) > 0):
          self.execsql(com,False)
      self.duplicate_db_recs = 0
      self.new_db_recs = 0
      self.db_conn.commit()
      self.log('done.\n')
      return True
    else:
      self.log('Table `%s`.`%s` already exists or error.\n' % (self.db_name,self.table_name))
      return False
  
  
  def voice_announce(self,announcement):
    if(self.announce):
      if(self.gui):
        if(self.timer2 and self.timer2.IsRunning()):
          # wait until prior announcement is complete
          self.timer3 = wx.Timer(self.gui_frame)
          self.gui_frame.Bind(wx.EVT_TIMER,lambda x:self.voice_announce(announcement), self.timer3,3)
          self.timer3.Start(1000,oneShot=True)
        else:
          # must use timer to keep from locking the main thread
          self.timer2 = wx.Timer(self.gui_frame)
          self.gui_frame.Bind(wx.EVT_TIMER, lambda x:self.voice_announce_core(announcement), self.timer2,2)
          self.timer2.Start(10,oneShot=True)
      else:
        self.voice_announce_core(announcement)
      
  def voice_announce_core(self,announcement):
    if(self.platform_windows):
      if(os.path.exists('speak.vbs')):
        os.system('speak.vbs "%s"' % announcement)
    else: # linux and others
      if(os.path.exists('speak.sh')):
        os.system('./speak.sh "%s"' % announcement)
    if(self.gui):
      self.timer2.Stop()
      self.timer2 = False
    
  
  def read_url_core(self):
    try:
      url = "http://%s" % (self.url_server)
      req = urllib2.Request(url)
      response = urllib2.urlopen(req)
      #print 'headers: " %s' % (response.headers.items())
      data = response.read()
      
      isbn = re.sub('(?s)[\s\S]*<textarea[\s\S]*?>([\s\S]*?)<[\s\S]*','\\1',data)
      # print ("ISBN: %s <> %s" % (isbn,self.old_isbn))
      # if old_isbn isn't set, set it to
      # current clipboard and resume
      if(self.old_isbn == False):
	self.old_isbn = isbn
	return True
      if(len(isbn) > 4 and self.old_isbn and self.old_isbn != isbn):
        self.log('Received ISBN from Server: %s\n' % isbn)
        self.voice_announce('New code received.')
        self.process_isbn(isbn,True)
      self.old_isbn = isbn
      return True
    except Exception as e:
      self.log('Clipboard monitor error: %s, stopping.\n' % str(e))
      return False
  
  def read_url_inner_comline(self):
    try:
      while(self._url_running):
        time.sleep(1)
        if(not self.read_url_core()):
          break
    except KeyboardInterrupt:
      return
      
  def read_url_inner_gui(self,x=False):
    if(not self.read_url_core()):
      return
    if(self._url_running and self._url_mode):
      self.timer = wx.Timer(self.gui_frame)
      self.gui_frame.Bind(wx.EVT_TIMER, self.read_url_inner_gui, self.timer,1)
      self.timer.Start(1000,oneShot=True)
    else:
      self.timer.Stop()
      self._url_running = False
      self.log('Closing URL monitoring mode.\n')
      self.show_results()
    
  def read_url_clipboard(self):
    self.log('Opening URL monitoring mode.\n')
    self.dc = random.randint(1000,1000000)
    self._url_running = True
    try:
      msg = ('(Ctrl+C to quit) ','')[self.gui]
      self.log('Monitoring Android clipboard at http://%s %s...\n' % (self.url_server,msg))
      self.old_isbn = False
      if(self.gui):
        self.read_url_inner_gui()
        return
      else:
        self.read_url_inner_comline()
    except Exception as e:
      self.log('URL clipboard monitor error: %s\n' % str(e))
    self._url_running = False
    self.log('Closing URL monitoring mode.\n')
  
  def rebuild_table(self):
    self.log('Rebuild database from stored JSON records ...\n')
    if(self.mysql_connect()):
      # rebuild table with preserved JSON files
      # if this script is invoked with option '-r'
      dirlist = os.listdir(self.isbndest)
      for fn in dirlist:
        isbn = re.sub('(?i)([\s\S]*)\.json','\\1',fn)
        self.process_isbn(isbn,False)
      self.db_conn.commit()
    self.log('Done.\n')
        
  def process_batch_codes(self):
    self.log('Processing files in "isbn_scanned_codes" subdirectory...\n')
    dirlist = os.listdir(self.isbnsrc)    
    for fn in dirlist:
      fullp = self.isbnsrc + "/" + fn
      if(re.search('\.zip$',fn)):
        zfile = zipfile.ZipFile(fullp)
        for name in zfile.namelist():
          data = zfile.read(name)
          self.process_isbn(data,True)
      else:
        data = self.read_file(fullp)
        self.process_isbn(data,True)
    self.log('Done.\n')
      
  def reset_values(self):
    self.error_isbn_codes = []
    self.scanned_entries = []
    self.user_entries = []
    self.new_db_recs = 0
    self.duplicate_db_recs = 0
    self.new_online_queries = 0
    self.data_errors = 0
    self.isbn_errors = 0
    
  def core_process(self):
    self.reset_values()
    if(self.create):
      self.create_db_table(self.db_name,self.table_name)
    if(self._url_mode):
      self.read_url_clipboard()
      if(self.gui):
        return
    else:
      self.process_batch_codes()
      if(self.rebuild_tbl):
        self.rebuild_table()
    self.show_results()
  
  # this is only called in command-line mode
    
  def process_console(self):
    if(not self.pw):
      self.pw = getpass.getpass(
        'Enter MySQL password for user %s: '
        % self.user_name
      )
    self.core_process()
    
  def show_results(self):    
    tot = self.new_db_recs+self.duplicate_db_recs
    
    fmtstr = \
"""Results:
      Records processed %d
      New records %d
      Duplicate records %s
      Online queries %d
      Data errors %s
      ISBN code errors %s
"""
       
    self.log(fmtstr %
        (tot,self.new_db_recs,
        self.duplicate_db_recs,
        self.new_online_queries,
        self.data_errors,
        self.isbn_errors
        )
      )
    
    if(self.verbose):
      if(self.isbn_errors > 0):
        self.log('Scanned codes that may need manual entry or review:\n')
        for err in self.error_isbn_codes:
          self.log('  %s\n' % err)
          
      self.list_verbose('Scanned',self.scanned_entries)
      self.list_verbose('User-entered',self.user_entries)
    if(not self.gui):
      self.quit_prompt()

if __name__ == "__main__":
  LibraryDB()
