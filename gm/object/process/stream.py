#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Copyright (c) 2017 TianJi Information Technology Inc.
'''
from __future__ import absolute_import

import os
import copy
import time
import random
import datetime

from pymongo import UpdateOne

import tornado.ioloop
from tornado.gen import coroutine
import framework
from framework import *

from . import Process
from gm.object.db import *
from gm.util import *
from gm.object.loganalyzer.analyzer import getChannelAndSubChannel
from gm.object.loganalyzer import startOfflineDaemon
from gm.object.archive import DBArchive as Archive
from gm.object.archive import DBDailyArchive as DailyArchive
from gm.object.account import DBAccount as Account
from gm.object.order import DBOrder as Order


class DBStreamProcess(Process):

	def __init__(self, cfg):
		self.cfg = cfg
		self.cursor = None
		self.dailyTimer = None
		# self.needAccountTags = False
		self.errOrderAccountID = None
		self.remainOrderData = None
		self.remainOrderDataCursor = None

		Process.__init__(self)

	def initCursor(self):
		cursor = {
			'cur_account_time': 0.0,
			'cur_order_time': 0.0,
			'cur_login_time': 0.0,
			'cur_order_amount': 0.0,
		}

		for curName in cursor:
			curValue = self.mongo.client.Cursor.find_one({'cur_name': curName})
			if not curValue:
				self.mongo.client.Cursor.insert_one({'cur_name': curName,
					'cur_value': cursor[curName]})
				continue
			cursor[curName] = curValue['cur_value']

		self.cursor = AttrsDict(cursor)
		self.logger.info('current cursor %s'% self.cursor)

	def saveCursor(self):
		data = []
		for curName in self.cursor.keys():
			data.append(UpdateOne({'cur_name': curName},
				{'$set': {'cur_value': self.cursor[curName]},}))

		self.mongo.client.Cursor.bulk_write(data)

	@coroutine
	def init(self):
		# mongo
		self.mongo = MongoDB(self.cfg['mongo'])
		self.AccountMongo = MongoDB(self.cfg['account_mongo'])
		self.PayOrderMongo = MongoDB(self.cfg['payorder_mongo'])

		# DB cache
		DBCache.Enabled = True

		# init cursor
		self.initCursor()

		self._onNewDay()

		# 设置每日统计定时器
		timerHour = datetime.time(hour=1)
		dtNow = nowdatetime_t()
		dtNext = datetime.datetime.combine(dtNow.date(), timerHour)
		if dtNow.time() > timerHour:
			dtNext += OneDay
		self.dailyTimer = tornado.ioloop.PeriodicCallback(self._onNewDay, 24 * 3600.0 * 1000.0, io_loop=self.ioloop)
		self.startAndTimer(dtNext, self.dailyTimer)

		# self.needAccountTags = self.cfg['need_account_tag'] #???

	def startAndTimer(self, dtNext, timer):
		def _run(timer):
			timer.start()
			return timer.callback()
		self.ioloop.add_timeout(dtNext - nowdatetime_t(), _run, timer)

	def _processNewAccount(self, account):
		# 如果订单都记录到本平台，那注册就算这平台的了
		# if not self.errOrderAccountID and ((account.tag != "") != self.needAccountTags):
		# 	return None

		createdDate = date2int(datetime.datetime.fromtimestamp(account.create_time).date())
		channel, subChannel = getChannelAndSubChannel(account)

		mongoAccount = DBFindOrCreate(self.mongo.client, Account, {'account_id': account._id})
		mongoAccount.set(account, channel, subChannel)

		key = {
			'date': createdDate,
			'channel': channel,
			'sub_channel': subChannel,
			'language': getServerLanguageByChannel(channel, subChannel),
			'area': 0,
		}

		# 注册统计
		archive = DBFindOrCreate(self.mongo.client, Archive, key)
		archive.addAccountCreated(account)

		# 登录统计
		loginDate = date2int(datetime.datetime.fromtimestamp(account.last_time).date())
		key['date'] = loginDate
		archive = DBFindOrCreate(self.mongo.client, Archive, key)
		archive.addAccountLogin(account)

		return mongoAccount

	def _processNewOrder(self, order):
		# 忽略不成功的
		if order.result != 'ok':
			return True

		# order.channel定义与account不同，是笼统的，所以取mongo里的account记录
		mongoAccount = DBFindOne(self.mongo.client, Account, {'account_id': order.account_id})
		if mongoAccount is None:
			self.errOrderAccountID = order.account_id
			self.logger.warning("account %s not be found in gm mongo", order.account_id)
			return False

		createdDate = date2int(datetime.datetime.fromtimestamp(order.time).date())

		# order 记录
		mongoOrder = DBFindOne(self.mongo.client, Order, {'order_id': order._id, 'channel_order_id': order.order_id})
		if mongoOrder is None:
			mongoOrder = DBCreateOne(self.mongo.client, Order, {'order_id': order._id, 'channel_order_id': order.order_id})
			language = getServerLanguageByKey(order.server_key)
			self.cursor.cur_order_amount += convertRecharge(order.recharge_id, language)
		mongoOrder.set(order, mongoAccount.channel, mongoAccount.sub_channel)

		key = {
			'date': createdDate,
			'channel': mongoAccount.channel,
			'sub_channel': mongoAccount.sub_channel,
			'language': getServerLanguageByChannel(mongoAccount.channel, mongoAccount.sub_channel),
			'area': getServerArea(order.server_key), # order分区统计
		}

		# order统计
		archive = DBFindOrCreate(self.mongo.client, Archive, key)
		archive.addOrder(order)
		# 有支付说明有登陆
		archive.addAccountAreaLogin(mongoAccount._id, order.time)

		# pay_orders 记录
		accountFirstPayTime = mongoAccount.addOrder(order)
		DBSave(self.mongo.client, mongoAccount)

		# 首次付费记录
		if accountFirstPayTime:
			firstPayDate = date2int(datetime.datetime.fromtimestamp(accountFirstPayTime).date())
			key.update({'date': firstPayDate})
			archive = DBFindOrCreate(self.mongo.client, Archive, key)
			archive.addAccountFirstPay(mongoAccount)

		return True

	def _processLoginAcccount(self, account):
		mongoAccount = DBFindOne(self.mongo.client, Account, {'account_id': account._id})
		if mongoAccount is None:
			mongoAccount = self._processNewAccount(account)
		else:
			channel, subChannel = getChannelAndSubChannel(account)
			mongoAccount.set(account, channel, subChannel)

		lastTime = datetime.datetime.fromtimestamp(account.last_time)
		loginDate = date2int(lastTime.date())

		key = {
			'date': loginDate,
			'channel': mongoAccount.channel,
			'sub_channel': mongoAccount.sub_channel,
			'language': getServerLanguageByChannel(mongoAccount.channel, mongoAccount.sub_channel),
			'area': 0,  # 账号不分区，这里account拿不到登录分区信息，只能从log里还原
		}

		# 登录统计
		archive = DBFindOrCreate(self.mongo.client, Archive, key)
		archive.addAccountLogin(account)

	def _processDaily(self, dateInt):
		daily = DBFindOrCreate(self.mongo.client, DailyArchive, {'date': dateInt})
		archives = DBFind(self.mongo.client, Archive, {'date': dateInt, 'language': framework.__language__}, noCache=True)
		for archive in archives:
			daily.addRecord(archive)
		DBSave(self.mongo.client, daily)
		return True

	def _onNewDay(self):
		dtNow = nowdatetime_t()
		self._processDaily(date2int(dtNow - OneDay))
		self._processDaily(date2int(dtNow))

	def run(self):
		super(DBStreamProcess, self).run()

		self.queueHandler = tornado.ioloop.PeriodicCallback(self.handleQueue, 2000, self.ioloop)
		self.accountDBHandler = tornado.ioloop.PeriodicCallback(self.handleAccountDB, 1000, self.ioloop)
		self.queueHandler.start()
		self.accountDBHandler.start()

		# 日志监听
		startOfflineDaemon(self.ioloop, self.logger, self.mongo, self.AccountMongo)

		self.ioloop.start()

	def handleQueue(self):
		if not self.taskDone:
			task = self.taskQueue.get_nowait()
			# try:
			func = getattr(self.console, task[0])
			func(*task[1:])
			# except Exception as e:
			# 	self.logger.warning('!! error handle task')
			# 	print task
			# 	print e

		if not self.stopSignal:
			return

		# 定时器关闭
		self.dailyTimer.stop()
		self.queueHandler.stop()
		self.accountDBHandler.stop()
		self.ioloop.stop()

		# 关闭mongo
		DBCache.saveAllMongo(self.mongo.client)
		self.AccountMongo.close()
		self.PayOrderMongo.close()
		self.mongo.close()

		self.logger.info('%s %x %x End', self.name, self.pid, id(self.ioloop))

	def handleAccountDB(self):
		# 限制每次处理的个数，但是有个问题，
		# 如果这1000个数据都是同一时间发生的，那这个时间点就过不去了，永远在循环
		# 最好就是不设置dbStep
		dbStep = 1000
		self.cursor.cur_login_time = min(self.cursor.cur_login_time, time.time())
		DBAccount = self.AccountMongo.client.Account
		DBOrder = self.PayOrderMongo.client.PayOrder
		nowTime = time.time()

		# new account-----------------------------------------
		if self.errOrderAccountID:
			# fix err account
			account = DBAccount.find_one({"_id": self.errOrderAccountID})
			if account:
				account = AttrsDict(account)
				self._processNewAccount(account)
			else:
				# account无法修复，就跳过该order
				self.logger.warning('account %s not existed, ignore order %s', self.errOrderAccountID, self.remainOrderData)
			self.errOrderAccountID = None

		query = {'create_time': {'$gte': self.cursor.cur_account_time}}
		field = {'name': 1, 'channel': 1, 'language': 1, 'pass_md5': 1, 'create_time': 1, 'last_time': 1}

		dataCursor = DBAccount.find(query, field).sort("create_time").limit(dbStep)
		for d in dataCursor:
			account = AttrsDict(d)
			self.cursor.cur_account_time = account.create_time
			self._processNewAccount(account)

		DBCache.saveAllMongo(self.mongo.client)
		self.cursor.cur_account_time = min(self.cursor.cur_account_time, nowTime)
		self.saveCursor()

		# new order-----------------------------------------
		if self.remainOrderData:
			# fix err order
			self._processNewOrder(self.remainOrderData)
			dataCursor = self.remainOrderDataCursor
			self.remainOrderData = None
			self.remainOrderDataCursor = None
		else:
			query = {'time': {'$gte': self.cursor.cur_order_time}}
			dataCursor = DBOrder.find(query).sort("time").limit(dbStep)

		for d in dataCursor:
			order = AttrsDict(d)
			self.cursor.cur_order_time = order.time
			if not self._processNewOrder(order):
				self.remainOrderData = order
				self.remainOrderDataCursor = dataCursor
				break

		DBCache.saveAllMongo(self.mongo.client)
		self.cursor.cur_order_time = min(self.cursor.cur_order_time, nowTime)
		self.saveCursor()

		# login account-------------------------------------------
		# if self.cfg['debug']:
		# 	self.cursor.cur_login_time = time.time()
		if nowTime - self.cursor.cur_login_time > 5*60.0:
			query = {'last_time': {'$gte': self.cursor.cur_login_time}}
			field = {'name': 1, 'channel': 1, 'language': 1, 'pass_md5': 1, 'create_time': 1, 'last_time': 1}
			dataCursor = DBAccount.find(query, field).sort("last_time").limit(dbStep)

			for d in dataCursor:
				account = AttrsDict(d)
				self._processLoginAcccount(account)
				self.cursor.cur_login_time = account.last_time

			DBCache.saveAllMongo(self.mongo.client)
			self.cursor.cur_login_time = min(self.cursor.cur_login_time, nowTime)
			self.saveCursor()
