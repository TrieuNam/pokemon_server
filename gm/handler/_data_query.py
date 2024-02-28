# -*- coding: utf-8 -*-
from __future__ import absolute_import

from tornado.gen import coroutine
from tornado.web import HTTPError
from framework import *

from .base import AuthedHandler
from gm.util import *
from gm.object.db import *
from gm.object.archive import DBDailyArchive, DBArchive
from gm.object.loganalyzer.archive import DBLogRoleArchive
from gm.object.account import DBAccount
from gm.object.order import DBOrder

import datetime
from collections import defaultdict


# 每日数据查询
class DailyHandler(AuthedHandler):
	url = r'/daily'

	@coroutine
	def get(self):
		self.render_page('_daily.html')

	@coroutine
	def post(self):
		r = self.get_json_data()
		startDate = r.get("startDate", None) # 20191215, int
		endDate = r.get("endDate", None) # 20191215, int
		servName = r.get("servName", "All")
		channel = r.get("channel", "All")
		fixday = r.get("fixday", "false") != "false"

		if self.isShuGuoAccount():
			channel = 'shuguo'
		if None in (startDate, endDate):
			raise HTTPError(404, 'no date')
		if servName != "All" and servName not in self.servsList:
			raise HTTPError(404, 'no this server')
		if channel != "All" and channel not in self.channelCache:
			raise HTTPError(404, 'no this channel')

		columns = [
			{'field': 'date', 'title': '日期', 'sortable': True},
			{'field': 'create', 'title': '新增账号', 'sortable': True},
			{'field': 'login', 'title': '登录账号', 'sortable': True},
			{'field': 'pay_count', 'title': '付费账号', 'sortable': True},
			{'field': 'pay_amount', 'title': '付费总额', 'sortable': True},
			{'field': 'ARPU', 'title': 'ARPU',},
			{'field': 'ARPPU', 'title': 'ARPPU',},
			{'field': 'payRate', 'title': '付费率',},
			{'field': 'payCountByCreated', 'title': '新增付费账号',},
			{'field': 'payAmountByCreated', 'title': '新增付费总额',},
			{'field': 'payRateByCreated', 'title': '新增付费率',},
			{'field': 'firstPayAccount', 'title': '首次付费账号',},
		]

		query = self.getQueryByServAndChannel(servName, channel)
		days = self.defaultDays(startDate, endDate)

		if servName == 'All' and channel == 'All':
			self.getDailyArchive(days, fixday)
		else:
			self.paddingArchiveDays(query, days)

		result = []
		sumArchive = DBDailyArchive(DBDailyArchive.defaultDocument())
		for date in sorted(days.keys()):
			archive = days[date]
			statistics = archive.statistics
			statistics.update({'date': date})
			result.append(statistics)
			sumArchive.addDailyRecord(archive)

		sumStatistics = sumArchive.statistics
		sumStatistics.update({'date': 'sum'})
		result.append(sumStatistics)

		columns = self.setLocalColumns(columns)
		self.write({
			'columns': columns,
			'data': result,
		})


# 次留数据查询
class RetentionHandler(AuthedHandler):
	url = r'/retention'

	@coroutine
	def get(self):
		self.render_page('_retention.html')

	@coroutine
	def post(self):
		r = self.get_json_data()
		servName = r.get("servName", "All")
		channel = r.get("channel", "All")
		startDate = r.get("startDate", None)
		endDate = r.get("endDate", None)
		tag = r.get("tag")

		self.errorHandler(servName=servName, channel=channel,
			startDate=startDate, endDate=endDate)

		columns = [
			{'field': 'date', 'title': '日期', 'sortable': True,},
			{'field': 'create', 'title': '新增账号',},
			{'field': 'login', 'title': '登录账号',},
			{'field': 'd2rate', 'title': '次留(率)', 'align': 'center'},
			{'field': 'd3rate', 'title': '3留(率)', 'align': 'center'},
			{'field': 'd4rate', 'title': '4留(率)', 'align': 'center'},
			{'field': 'd5rate', 'title': '5留(率)', 'align': 'center'},
			{'field': 'd6rate', 'title': '6留(率)', 'align': 'center'},
			{'field': 'd7rate', 'title': '7留(率)', 'align': 'center'},
			{'field': 'd15rate', 'title': '15留(率)', 'align': 'center'},
			{'field': 'd30rate', 'title': '30留(率)', 'align': 'center'},
			{'field': 'd60rate', 'title': '60留(率)', 'align': 'center'},
			{'field': 'd90rate', 'title': '90留(率)', 'align': 'center'},
			{'field': 'd180rate', 'title': '180留(率)', 'align': 'center'},
		]

		endDate7 = date2int(datetime.datetime.combine(int2date(endDate), datetime.time()) + datetime.timedelta(days=6))
		if tag == 'role-info':
			query = {} if servName == "All" else {'server_key': servName}
			days = self.defaultDays(startDate, endDate7, True)
		else:
			query = self.getQueryByServAndChannel(servName, channel)
			days = self.defaultDays(startDate, endDate7) # {date: DBDailyArchive}

		queryDateInts = {}
		dateInts = set()
		s = datetime.datetime.combine(int2date(startDate), datetime.time())
		e = datetime.datetime.combine(int2date(endDate), datetime.time())
		while s <= e:
			lst = [date2int(s + (i + 1) * OneDay) for i in xrange(6)]
			lst += [date2int(s + datetime.timedelta(days=14)), date2int(s + datetime.timedelta(days=29)),
				date2int(s + datetime.timedelta(days=59)), date2int(s + datetime.timedelta(days=89)),
				date2int(s + datetime.timedelta(days=179))]
			queryDateInts[date2int(s)] = lst
			dateInts |= set(lst)
			s += OneDay

		for d in dateInts:
			if d in days:
				continue
			if tag == 'role-info':
				days[d] = DBLogRoleArchive(DBLogRoleArchive.defaultDocument(date=d))
			else:
				days[d] = DBDailyArchive(DBDailyArchive.defaultDocument(d))

		if tag == 'role-info':
			self.paddingArchiveDays(query, days, True)
		else:
			if servName == 'All' and channel == 'All':
				self.getDailyArchive(days)
			else:
				self.paddingArchiveDays(query, days)

		result = []
		fields = ['d2', 'd3', 'd4', 'd5', 'd6', 'd7', 'd15', 'd30', 'd60', 'd90', 'd180']
		for dateInt in sorted(queryDateInts.keys()):
			day = days[dateInt]
			d = {'date': dateInt}
			d['create'] = day.sum.get('create', 0)
			d['login'] = day.sum.get('login', 0)

			for i, futureInt in enumerate(queryDateInts[dateInt]):
				future = days[futureInt]

				if futureInt > todaydate2int():
					total, rate = '-', '-'
				else:
					total, rate = day.retentionRateWith(future)
					rate = '%.2f%%' % round(rate, 2)
				d[fields[i] + 'rate'] = '%s ( %s )' % (total, rate)
			result.append(d)

		columns = self.setLocalColumns(columns)
		self.write({
			'columns': columns,
			'data': result,
		})


# 充值详情
class RechargeHandler(AuthedHandler):
	url = r'/recharge'

	@coroutine
	def get(self):
		self.render_page("_recharge.html")

	@coroutine
	def post(self):
		r = self.get_json_data()
		startDate = r.get("startDate", None)
		endDate = r.get("endDate", None)
		servName = r.get("servName", "All")
		roleID = r.get("roleID", None)
		accountID = r.get("accountID", None)
		sdkAccount = r.get("sdkAccount", None)
		channelOrderID = r.get("channelOrderID", None)

		if servName != "All" and servName not in self.servsList:
			raise HTTPError(404, 'no this server')

		columns = [
			{'field': 'date', 'title': '日期', 'sortable': True},
			{'field': 'account_id', 'title': '账号ID'},
			{'field': 'channel', 'title': '渠道'},
			{'field': 'server_key', 'title': '服务器'},
			{'field': 'role_id', 'title': '角色ID'},
			{'field': 'amount', 'title': '充值额'},
			{'field': 'channel_order_id', 'title': '渠道订单号'},
		]

		startTime = time.mktime(int2date(startDate).timetuple())
		endTime = time.mktime(int2date(endDate).timetuple()) + 24 * 3600.0
		query = {
			'time': {'$gte': startTime, '$lte': endTime},
		}

		# 单账号
		if accountID:
			query['account_id'] = int(accountID)
		# 单角色
		if roleID:
			query['role_id'] = int(roleID)
		# 单区服
		if servName != "All":
			query['server_key'] = servName
		# 渠道帐号,name也是唯一的？？
		if sdkAccount:
			accountList = DBFind(self.mongo_client, DBAccount, {'name': sdkAccount})
			accountIdList = [account.account_id for account in accountList]
			query['account_id'] = {'$in': accountIdList}
		# 渠道订单号
		if channelOrderID:
			query['channel_order_id'] = {'$regex': '.*%s.*' % channelOrderID}

		result = []
		orders = DBFind(self.mongo_client, DBOrder, query, sort='time', noCache=True)
		for order in orders:
			d = order.toDict()
			d.pop('_id', None)
			d['date'] = str(datetime.datetime.fromtimestamp(order.time))
			d['amount'] = self.RechargeMap[order.recharge_id]
			result.append(d)

		result = hexlifyDictField(result)
		columns = self.setLocalColumns(columns)
		self.write({
			'columns': columns,
			'data': result,
		})


# 充值排行
class RechargeRankAllhandler(AuthedHandler):
	url = r'/recharge_rank'

	@coroutine
	def get(self):
		self.render_page('_recharge_rank.html')

	@coroutine
	def post(self):
		r = self.get_json_data()
		servName = r.get("servName", "All")
		channel = r.get("channel", "All")
		offset = r.get("offset", 0)
		limit = r.get("limit", 10)

		self.errorHandler(servName=servName, channel=channel)

		columns = [
			{'field': 'rank', 'title': '排名'},
			{'field': 'accountID', 'title': '账号ID', },
			{'field': 'channel', 'title': '渠道', },
			# {'field': 'roleID', 'title': '角色ID', },
			# {'field': 'level', 'title': '等级', },
			{'field': 'rechargeAmount', 'title': '充值金额', },
			# {'field': 'diamonds', 'title': '充值钻石', },
			{'field': 'rechargeTimes', 'title': '充值次数', },
			{'field': 'recentRechargeTime', 'title': '最近充值时间', },
			# {'field': 'proportion', 'title': '占总充值比', },
			{'field': 'recentLoginTime', 'title': '最近登陆时间', },
		]

		query = self.getQueryByServAndChannel(servName, channel)
		query.pop('language', None) # Order和Account没有语言区分
		result = []

		# 查询所有服务器，查询账户
		if servName == 'All':
			q = {'pay_amount': {'$gt': 0}}
			q.update(query)
			accountList = DBFind(self.mongo_client, DBAccount, q, sort=[('pay_amount', -1)], limit=limit, skip=offset)
			sumCount = DBCount(self.mongo_client, DBAccount, q)

			def pushResult(account, rank):
				a = {}
				a['rank'] = rank
				a['accountID'] = account.account_id
				a['channel'] = account.sub_channel if 'sub_channel' in query else account.channel
				a['rechargeAmount'], a['recentRechargeTime'] = self.getAllOrderAmount(account, query)
				a['rechargeTimes'] = len(account.pay_orders)
				a['recentLoginTime'] = str(datetime.datetime.fromtimestamp(account.last_time)),
				result.append(a)
				return a['rechargeAmount']

			totalAmount = 0
			for rank, account in enumerate(accountList, offset+1):
				totalAmount += pushResult(account, rank)

			rows = hexlifyDictField(result)
			total = sumCount

		#如果不是所有服务器，查询订单类
		elif servName != 'All':
			query['server_key'] = servName
			query.pop('area', None)
			orderList = DBFind(self.mongo_client, DBOrder, query)
			accountTransitDict = defaultdict(lambda: AttrsDict({'orders': [], 'time': 0, 'channel': None}))

			for order in orderList:
				accountID = order.account_id
				account = DBFindOne(self.mongo_client, DBAccount, {'account_id': accountID})
				chnlOrSubchnl = account.sub_channel if account.sub_channel != 'none' else account.channel
				orderAmount = self.RechargeMap[order.recharge_id]
				# 如果账号转化列表里有，则充值金额dict里加入订单金额，比较订单时间/更新，计算当前账户充值总额
				accountTransitDict[accountID].orders.append(orderAmount)
				accountTransitDict[accountID].time = max(order.time, accountTransitDict[accountID].time)
				accountTransitDict[accountID].channel = chnlOrSubchnl

			# 排序
			tempList = sorted(accountTransitDict.iteritems(), key=lambda d: sum(d[1].orders), reverse=True)
			result = []
			for rank, t in enumerate(tempList, 1):
				accountID, info = t
				result.append({
					'rank': rank,
					'accountID': accountID,
					'channel': info.channel,
					'rechargeAmount': sum(info.orders),
					'recentRechargeTime': str(datetime.datetime.fromtimestamp(info.time)),
					'rechargeTimes': len(info.orders),
				})

			total = len(result)
			rows = hexlifyDictField(result[offset: offset+limit])

		columns = self.setLocalColumns(columns)
		self.write({
			'limit': limit,
			'offset': offset,
			'columns': columns,
			'data': {
				"total": total,
				"rows": rows,
			}
		})


# 充值图表
class RechargeChartHandler(AuthedHandler):
	url = r'/recharge_chart'

	@coroutine
	def get(self):
		self.render_page('_recharge_chart.html')

	@coroutine
	def post(self):
		r = self.get_json_data()
		startDate = r.get("startDate")
		endDate = r.get("endDate")
		servName = r.get("servName", "All")

		startTime = time.mktime(int2date(startDate).timetuple())
		endTime = time.mktime(int2date(endDate).timetuple()) + 24 * 3600.0
		query = {
			'time': {'$gte': startTime, '$lte': endTime},
		}
		#单区服
		if servName != "All":
			query['server_key'] = servName

		ret = defaultdict(int)
		if startDate == endDate:
			t = int2datetime((startDate - 20000000) * 100)
			e = t + OneDay
			while t < e:
				ret[datetime2int(t)] = 0
				t += OneHour
		else:
			t = int2date(startDate)
			e = int2date(endDate)
			while t <= e:
				ret[date2int(t)] = 0
				t += OneDay

		orders = DBFind(self.mongo_client, DBOrder, query, sort='time', noCache=True)
		for order in orders:
			if startDate == endDate:
				ret[datetime2int(datetime.datetime.fromtimestamp(
					order.time))] += self.RechargeMap[order.recharge_id]
			else:
				ret[date2int(datetime.datetime.fromtimestamp(
					order.time))] += self.RechargeMap[order.recharge_id]

		labels = []
		datas = []
		for k, v in sorted(ret.items(), key=lambda d: d[0]):
			if startDate == endDate:
				labels.append(str(k)[-2:])
			else:
				labels.append(k)
			datas.append(v)

		self.write({
				'labels': labels,
				'datas': datas
			})


# 流失统计
class LostHandler(AuthedHandler):
	url = r'/lost'

	@coroutine
	def get(self):
		self.render_page('_lost.html')

	@coroutine
	def post(self):
		r = self.get_json_data()
		servName = r.get('servName', 'All')
		channel = r.get("channel", "All")
		startDate = r.get("startDate", None)
		endDate = r.get("endDate", None)
		self.errorHandler(channel=channel, startDate=startDate, endDate=endDate)

		columns = [
			{'field': 'date', 'title': '日期', 'sortable': True,},
			{'field': 'added', 'title': '新增'},
			{'field': 'login', 'title': '登录'},
			{'field': 'd3lost', 'title': '3天内未登录',},
			{'field': 'd7lost', 'title': '7天内未登录',},
			{'field': 'd15lost', 'title': '15天内未登录',},
		]

		s = datetime.datetime.combine(int2date(startDate), datetime.time())
		e = datetime.datetime.combine(int2date(endDate), datetime.time())
		days = self.defaultDays(s, e + 15*OneDay)

		queryDateInts = {}
		while s <= e:
			lst = [date2int(s + (i + 1) * OneDay) for i in xrange(15)]
			queryDateInts[date2int(s)] = lst
			s += OneDay

		if servName == 'All' and channel == 'All':
			self.getDailyArchive(days)
		else:
			query = self.getQueryByServAndChannel(servName, channel)
			self.paddingArchiveDays(query, days)

		result = []
		for dateInt in sorted(queryDateInts.keys()):
			day = days[dateInt]
			d = {'date': dateInt}
			d["added"] = day.sum.get('create', 0)
			d['login'] = day.sum.get('login', 0)

			futureList = [days[index] for index in sorted(queryDateInts[dateInt])]
			d['d3lost'] = day.lostNumber(futureList[:3])
			d['d7lost'] = day.lostNumber(futureList[:7])
			d['d15lost'] = day.lostNumber(futureList)
			result.append(d)

		result = hexlifyDictField(result)
		columns = self.setLocalColumns(columns)
		self.write({
			'columns': columns,
			'data': result,
		})


# LifeTimeValue
class LTVHander(AuthedHandler):
	url = r'/ltv'

	@coroutine
	def get(self):
		self.render_page('_ltv.html')

	@coroutine
	def post(self):
		r = self.get_json_data()
		startDate = r.get("startDate", None)
		endDate = r.get("endDate", None)
		serverName = r.get("servName", "All")
		channel = r.get("channel", "All")
		self.errorHandler(servName=serverName, channel=channel, startDate=startDate, endDate=endDate)

		startTime, endTime = time.mktime(int2date(startDate).timetuple()), time.mktime(int2date(endDate).timetuple()) + 60 * 60 * 24
		duration =  (endTime - startTime) / (3600 * 24)

		columns = [
			{'field': 'date', 'title': '日期', 'sortable': True, },
			{'field': 'Added', 'title': '新增', },
			{'field': '7pay', 'title': '7日总付费', },
			{'field': '7ltv', 'title': '7日LTV', },
			{'field': '14pay', 'title': '14日总付费', },
			{'field': '14ltv', 'title': '14日LTV', },
			{'field': '30pay', 'title': '30日总付费', },
			{'field': '30ltv', 'title': '30日LTV', },
			{'field': '60pay', 'title': '60日总付费', },
			{'field': '60ltv', 'title': '60日LTV', },
			{'field': '90pay', 'title': '90日总付费', },
			{'field': '90ltv', 'title': '90日LTV', },
		]
		cursorColumn = [
			{'field': '%dpay' % duration, 'title': '%d日总付费' % duration },
			{'field': '%dltv' % duration, 'title': '%d日LTV' % duration, },
		]
		cursor = 0
		if 0 <= duration <= 7:
			cursor = 2
		elif 7 < duration <= 14:
			cursor = 4
		elif 14 < duration <= 30:
			cursor = 6
		elif 30 < duration <= 60:
			cursor = 8
		elif 60 < duration <= 90:
			cursor = 10
		elif 90 < duration:
			cursor = 12
		columns = columns[:cursor] + cursorColumn + columns[cursor:]

		query = {'time': {'$gte': startTime, '$lt': endTime + 90 * 24 * 60 * 60}}
		query_account = {'create_time': {'$gte': startTime, '$lt': endTime}}

		if serverName != "All":
			query["server_key"] = serverName

		subChannel = self.getSubChannel(channel)
		if subChannel:
			query['sub_channel'] = subChannel
			query_account['sub_channel'] = subChannel
		elif channel != 'All':
			query['channel'] = channel
			query_account['channel'] = channel

		dateMap = defaultdict(list) # date: [account_id,]
		accCreateTimeMap = defaultdict(lambda: datetime.date(year=2000, month=1, day=1)) # account_id: create_time
		detailMap = defaultdict(list) # account_id: [(order_time, order_time-create_time, money),]

		accountList = DBFind(self.mongo_client, DBAccount, query_account)
		for account in accountList:
			dt = datetime.datetime.fromtimestamp(account.create_time)
			accCreateTimeMap[account.account_id] = dt.date()
			dateMap[dt.date()].append(account.account_id)

		orderList = DBFind(self.mongo_client, DBOrder, query)
		for order in orderList:
			dt = datetime.datetime.fromtimestamp(order.time).date()
			money = self.RechargeMap[order.recharge_id]
			detailMap[order.account_id].append((dt, dt - accCreateTimeMap[order.account_id], money))

		day90 = datetime.timedelta(days=90)
		day60 = datetime.timedelta(days=60)
		day30 = datetime.timedelta(days=30)
		day14 = datetime.timedelta(days=14)
		day7 = datetime.timedelta(days=7)
		dayX = datetime.timedelta(days=duration)

		result = []
		dts = sorted(dateMap.keys())
		for dt in dts:
			d = dict()
			d["date"] = date2int(dt)
			accL = dateMap[dt]
			s90, s60, s30, s14, s7, sX = 0, 0, 0, 0, 0, 0
			for accountID in accL:
				for pay in detailMap[accountID]:
					s90 += pay[-1] if pay[1] <= day90 else 0
					s60 += pay[-1] if pay[1] <= day60 else 0
					s30 += pay[-1] if pay[1] <= day30 else 0
					s14 += pay[-1] if pay[1] <= day14 else 0
					s7 += pay[-1] if pay[1] <= day7 else 0
					sX += pay[-1] if pay[1] <= dayX else 0

			d.update({
				"Added": len(accL),
				"7pay": s7,
				"7ltv": round(1.0 * s7 / len(accL), 2),
				"14pay": s14,
				"14ltv": round(1.0 * s14 / len(accL), 2),
				"30pay": s30,
				"30ltv": round(1.0 * s30 / len(accL), 2),
				"60pay": s60,
				"60ltv": round(1.0 * s60 / len(accL), 2),
				"90pay": s90,
				"90ltv": round(1.0 * s90 / len(accL), 2),
				"%dpay" % duration: sX,
				"%dltv" % duration: round(1.0 * sX / len(accL), 2),
			})
			result.append(d)

		columns = self.setLocalColumns(columns)
		self.write({
			"columns": columns,
			"data": result
		})


# 今日在线玩家
class OnlineHandler(AuthedHandler):
	url = '/online_player'

	@coroutine
	def get(self):
		self.render_page('_gamedata.html')

	@coroutine
	def post(self):
		r = self.get_json_data()
		date = r.get("date", None)
		serverName = r.get("servName", "All")
		channel = r.get("channel", "All")

		self.errorHandler(servName=serverName, channel=channel)
		query = self.getQueryByServAndChannel(serverName, channel)

		if date:
			query.update({'date': date})
			archives = DBFind(self.mongo_client, DBArchive, query)

		query.update({'date': todaydate2int()})
		archivesToday = DBFind(self.mongo_client, DBArchive, query)

		query.update({'date': date2int(nowdate_t() - OneDay)})
		archivesYesterday = DBFind(self.mongo_client, DBArchive, query)

		def _c(archiveList, dt):
			ret = defaultdict(int)
			t = datetime.datetime(year=dt.year, month=dt.month, day=dt.day)
			e = t + OneDay
			while t < e:
				ret[datetime2int(t)] = 0
				t += OneHour

			for archive in archiveList:
				for loginHour, loginAccountList in archive.login_time.iteritems():
					ret[int(loginHour)] += len(loginAccountList)

			labels = []
			datas = []
			for k, v in sorted(ret.items(), key=lambda d: d[0]):
				labels.append(k % 100)
				datas.append(v)

			return labels, datas

		datas = {}
		tdate = nowdate_t()
		labels, datas['today'] = _c(archivesToday, tdate)
		tdate = nowdate_t() - OneDay
		_, datas['yesterday'] = _c(archivesYesterday, tdate)
		if date:
			tdate = int2date(date)
			_, datas['choice'] = _c(archives, tdate)

		self.write({
				'labels': labels,
				'datas': datas
			})