#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
Copyright (c) 2017 TianJi Information Technology Inc.

Operation Handlers
'''
from __future__ import absolute_import

from .base import AuthedHandler
from gm.util import *
from gm.object.db import *
from gm.object.account import DBAccount
from gm.object.archive import DBArchive, DBDailyArchive
from gm.object.order import DBOrder

import datetime
import time
from itertools import izip_longest
from urllib2 import HTTPError

from tornado.gen import coroutine, Return
from collections import defaultdict

import framework
from framework import *


# 运营数据
class OperationHandler(AuthedHandler):
	url = r'/operation_data'

	@coroutine
	def run(self):
		_ajax = self.get_argument("_ajax", False)
		self.renderHandler(_ajax, "operation.html", channelList=True)

		servName = self.get_argument("servName", None)
		channel = self.get_argument("channel", None)
		subChannel = self.get_argument("subChannel", None)

		ret = {
			"战士": 30,
			"坦克": 325,
			"法师": 798,
			"辅助": 899
		}
		self.write(ret)


# 玩家等级分布
class LevelCheckHandler(AuthedHandler):
	url = r'/level_check'

	@coroutine
	def run(self):
		_ajax = self.get_argument("_ajax", False)
		self.renderHandler(_ajax, "operation.html", channelList=True)

		servName = self.get_argument("servName", None)
		channel = self.get_argument("channel", None)
		subChannel = self.get_argument("subChannel", None)

		ret = {
			1: 83,
			2: 89,
			5: 989,
			38: 100,
			98: 32,
			100: 32
		}

		self.write(ret)


# 战斗力排行榜
class FightingRankHandler(AuthedHandler):
	url = r'/fighting_rank'

	@coroutine
	def get(self):
		servName = self.get_argument("servName", None)

		sort = self.get_argument('sort', None)
		order = self.get_argument('order', None)
		offset = int(self.get_argument("offset", 0))
		limit = int(self.get_argument("limit", 0))

		if servName == "All":
			raise HTTPError(404, reason="servName error")

		result = []
		total = 0

		if limit:
			ret = yield self.userGMRPC.gmGetGameRank(self.session, servName, 'fight')
			ret = ret['view']['rank']
			total = len(ret)
			for i, d in enumerate(ret):
				d['role']['fighting_point'] = d.pop('fighting_point')
				d['role']['rank_id'] = i + 1
				result.append(d['role'])

			if sort:
				result = sorted(result, key=lambda r: r[sort], reverse=True if order=='asc' else False)

			result = result[offset: offset+limit]

			# print 'rrrrrrrrrrrrr', result
			rows = hexlifyDictField(result)
			self.write({
				"total": total,
				"rows": rows,
				"limit": limit,
				"offset": offset
			})
		else:
			 # 'fighting_point': 269233,
		  #   'role': {
		  #     'name': '\xe7\x82\xb9\xe7\x82\xb9\xe6\xbb\xb4\xe6\xbb\xb4',
		  #     'level': 100,
		  #     'frame': 1,
		  #     'title': 17,
		  #     'vip_level': 12,
		  #     'logo': 1,
		  #     'id': '\\\xba\xcf5\x80\xae\x88\x0f\x96\x10\n\x13
			columns = [
				{'field': 'rank_id', 'title': '排名', 'sortable': True},
				{'field': 'id', 'title': '角色ID'},
				{'field': 'name', 'title': '角色名'},
				{'field': 'level', 'title': '等级'},
				{'field': 'vip_level', 'title': 'VIP', 'sortable': True},
				{'field': 'fighting_point', 'title': '战力'},
				{'field': 'title', 'title': 'title'},
				{'field': 'frame', 'title': 'frame'},
				{'field': 'logo', 'title': 'logo'},
			]

			columns = self.setLocalColumns(columns)
			self.write({'columns': columns,})


# 竞技场排行榜
class PWRankHandler(AuthedHandler):
	url = r'/arena_rank'

	@coroutine
	def get(self):
		servName = self.get_argument("servName", None)
		sort = self.get_argument('sort', None)
		order = self.get_argument('order', None)
		offset = int(self.get_argument("offset", 0))
		limit = int(self.get_argument("limit", 0))

		if servName == "All":
			raise HTTPError(404, reason="servName error")

		result = []
		total = 0

		if limit:
			ret = yield self.userGMRPC.gmGetGameRank(self.session, servName, 'arena')
			result = ret['view']['rank']

			total = len(result)
			if sort:
				result = sorted(result, key=lambda r: r[sort], reverse=True if order=='asc' else False)

			result = result[offset: offset+limit]

			rows = hexlifyDictField(result)
			self.write({
				"total": total,
				"rows": rows,
				"limit": limit,
				"offset": offset
			})

		else:
			columns = [
				{'field': 'rank', 'title': '排名', 'sortable': True},
				{'field': 'name', 'title': '名称'},
				{'field': 'level', 'title': '等级'},
				{'field': 'role_db_id', 'title': 'db_id'},
				{'field': 'record_id', 'title': 'record_id'},
				{'field': 'fighting_point', 'title': 'fighting_point'},
				{'field': 'frame', 'title': 'frame'},
				{'field': 'display', 'title': 'display'},
				{'field': 'logo', 'title': 'logo'},
			]

			columns = self.setLocalColumns(columns)
			self.write({'columns': columns})


# 收藏排行
class PokedexRankHandler(AuthedHandler):
	url = r'/pokedex_rank'

	@coroutine
	def get(self):
		servName = self.get_argument("servName", None)
		sort = self.get_argument('sort', None)
		order = self.get_argument('order', None)
		offset = int(self.get_argument("offset", 0))
		limit = int(self.get_argument("limit", 0))

		if servName == "All":
			raise HTTPError(404, reason="servName error")

		result = []
		total = 0

		if limit:
			ret = yield self.userGMRPC.gmGetGameRank(self.session, servName, 'pokedex')
			# 排序
			ret = sorted(ret['view']['rank'], key=lambda d: d["pokedex"], reverse=True)

			for i, d in enumerate(ret):
				d['role']['pokedex'] = d.pop('pokedex')
				d['role']['rank_id'] = i + 1
				result.append(d['role'])

			total = len(result)
			if sort:
				# 表排序
				result = sorted(result, key=lambda r: r[sort], reverse=True if order=='asc' else False)
			result = result[offset: offset+limit]

			rows = hexlifyDictField(result)
			self.write({
				"total": total,
				"rows": rows,
				"limit": limit,
				"offset": offset
			})

		else:
			# {
		 #        'role': {
		 #          'name': 'zxf12',
		 #          'level': 100,
		 #          'frame': 1,
		 #          'title': 1,
		 #          'vip_level': 12,
		 #          'logo': 1,
		 #          'id': '\\\xbdk\xdd\x80\xae\x88|*\x82\xdc\xb3'
		 #        },
		 #        'pokedex': 101
		 #      },
			columns = [
				{'field': 'rank_id', 'title': '排名', 'sortable': True,},
				{'field': 'pokedex', 'title': '收藏率'},
				{'field': 'name', 'title': '玩家名称'},
				{'field': 'id', 'title': 'roleID'},
				{'field': 'level', 'title': '玩家等级'},
				{'field': 'vip_level', 'title': 'VIP'},
				{'field': 'title', 'title': 'title'},
				{'field': 'frame', 'title': 'frame'},
				{'field': 'logo', 'title': 'logo'},
			]

			columns = self.setLocalColumns(columns)
			self.write({'columns': columns})


# # 星级排行榜
# class StarsRankHandler(AuthedHandler):
# 	url = r'/stars_rank'

# 	@coroutine
# 	def get(self):
# 		servName = self.get_argument("servName", None)
# 		offset = int(self.get_argument("offset", 0))
# 		limit = int(self.get_argument("limit", 0))

# 		if servName == "All":
# 			raise HTTPError(404, reason="servName error")



# 		fields = ['roleID', 'unknown', 'name', 'level', 'fight_power', 'union_name', 'stars', 'logo_frame']

# 		result = []
# 		total = 0

# 		if limit:
# 			ret = yield self.userGMRPC.gmGetGameRank(self.session, servName, 'star')
# 			ret = ret['view']['rank']
# 			total = len(ret)
# 			start = offset * limit
# 			for t in ret:
# 				start = start + 1
# 				r = {'id': start}
# 				for i, items in enumerate(t):
# 					r[fields[i]] = items
# 				result.append(r)

# 			rows = hexlifyDictField(result)
# 			self.write({
# 				"total": total,
# 				"rows": rows,
# 				"limit": limit,
# 				"offset": offset
# 			})
# 		else:
# 			columns = [
# 				{'field': 'id', 'title': '排名'},
# 				{'field': 'roleID', 'title': '角色ID'},
# 				{'field': 'name', 'title': '角色名'},
# 				{'field': 'level', 'title': '等级'},
# 				{'field': 'fight_power', 'title': '战斗力'},
# 				{'field': 'union_name', 'title': '工会'},
# 				{'field': 'stars', 'title': '关卡星级'},
# 			]

# 			columns = self.setLocalColumns(columns)
# 			self.write({
# 				'columns': columns,
# 			})


# # 训兽排行榜
# class CardNumRankHandler(AuthedHandler):
# 	url = r'/cardNum_rank'

# 	@coroutine
# 	def get(self):
# 		servName = self.get_argument("servName", None)

# 		sort = self.get_argument('sort', None)
# 		order = self.get_argument('order', None)
# 		offset = int(self.get_argument("offset", 0))
# 		limit = int(self.get_argument("limit", 0))

# 		if servName == "All":
# 			raise HTTPError(404, reason="servName error")

# 		fields = ['roleID', 'unknown', 'name', 'level', 'vip_level', 'union_name', 'cardNum', 'logo_frame']

# 		result = []
# 		total = 0

# 		if limit:
# 			ret = yield self.userGMRPC.gmGetGameRank(self.session, servName, 'cardNum')
# 			ret = ret['view']['rank']
# 			total = len(ret)
# 			start = offset * limit
# 			for t in ret:
# 				start = start + 1
# 				r = {'id': start}
# 				for i, items in enumerate(t):
# 					if fields[i] == 'cardNum':
# 						from game.object.game.rank import FightGoVal_Max
# 						r[fields[i]] = items / FightGoVal_Max
# 					else:
# 						r[fields[i]] = items
# 				result.append(r)

# 			if sort:
# 				result = sorted(result, key=lambda r: r[sort], reverse=True if order=='asc' else False)

# 			rows = hexlifyDictField(result)
# 			self.write({
# 				"total": total,
# 				"rows": rows,
# 				"limit": limit,
# 				"offset": offset
# 			})
# 		else:
# 			columns = [
# 				{'field': 'id', 'title': '排名', 'sortable': True},
# 				{'field': 'roleID', 'title': '角色ID'},
# 				{'field': 'name', 'title': '角色名'},
# 				{'field': 'level', 'title': '等级'},
# 				{'field': 'vip_level', 'title': 'VIP', 'sortable': True},
# 				{'field': 'union_name', 'title': '工会'},
# 				{'field': 'cardNum', 'title': '卡牌数'},
# 			]

# 			columns = self.setLocalColumns(columns)
# 			self.write({
# 				'columns': columns,
# 			})


# # 试炼排行榜
# class TowerRankHandler(AuthedHandler):
# 	url = r'/trails_rank'

# 	@coroutine
# 	def get(self):
# 		servName = self.get_argument("servName", None)

# 		sort = self.get_argument('sort', None)
# 		order = self.get_argument('order', None)
# 		offset = int(self.get_argument("offset", 0))
# 		limit = int(self.get_argument("limit", 0))

# 		if servName == "All":
# 			raise HTTPError(404, reason="servName error")

# 		fields = ['roleID', 'unknown', 'name', 'level', 'vip_level', 'union_name', 'score', 'logo_frame']

# 		result = []
# 		total = 0

# 		if limit:
# 			ret = yield self.userGMRPC.gmGetGameRank(self.session, servName, 'yuanzheng')
# 			ret = ret['view']['rank']
# 			total = len(ret)
# 			start = offset * limit
# 			for t in ret:
# 				start = start + 1
# 				r = {'id': start}
# 				for i, items in enumerate(t):
# 					if fields[i] == 'score':
# 						from game.object.game.rank import YzRankFloor_Max
# 						score = items / 10000000000
# 						day_point = score / YzRankFloor_Max
# 						yz_pass_floor = score % YzRankFloor_Max
# 						r['tower'] = yz_pass_floor
# 						r['day_point'] = day_point
# 					else:
# 						r[fields[i]] = items
# 				result.append(r)

# 			if sort:
# 				result = sorted(result, key=lambda r: r[sort], reverse=True if order=='asc' else False)

# 			rows = hexlifyDictField(result)
# 			self.write({
# 				"total": total,
# 				"rows": rows,
# 				"limit": limit,
# 				"offset": offset
# 			})
# 		else:
# 			columns = [
# 				{'field': 'id', 'title': '排名', 'sortable': True},
# 				{'field': 'roleID', 'title': '角色ID'},
# 				{'field': 'name', 'title': '角色名'},
# 				{'field': 'level', 'title': '等级'},
# 				{'field': 'vip_level', 'title': 'VIP', 'sortable': True},
# 				{'field': 'union_name', 'title': '工会'},
# 				{'field': 'tower', 'title': '塔层'},
# 				{'field': 'day_point', 'title': '每日积分'},
# 			]

# 			columns = self.setLocalColumns(columns)
# 			self.write({
# 				'columns': columns,
# 			})


# # 工会排行榜
# class UnionRankHandler(AuthedHandler):
# 	url = r'/union_rank'

# 	@coroutine
# 	def get(self):
# 		servName = self.get_argument("servName", None)
# 		offset = int(self.get_argument("offset", 0))
# 		limit = int(self.get_argument("limit", 0))

# 		if servName == "All":
# 			raise HTTPError(404, reason="servName error")

# 		columns = [
# 			{'field': 'ID', 'title': '排名'},
# 			{'field': 'id', 'title': '工会ID'},
# 			{'field': 'name', 'title': '工会名'},
# 			{'field': 'level', 'title': '工会等级'},
# 			{'field': 'members', 'title': '工会人数'},
# 			{'field': 'intro', 'title': '工会简介'},
# 			{'field': 'contrib', 'title': '总贡献值'},
# 			{'field': 'day_contrib', 'title': '当日贡献'},
# 			{'field': 'join_type', 'title': '加入类型'},
# 			{'field': 'join_level', 'title': '加入等级限制'},
# 		]

# 		ret = []
# 		total = 0

# 		if limit:
# 			ret = yield self.userGMRPC.gmGetGameRank(self.session, servName, 'union')
# 			ret = ret['view']['rank']
# 			total = len(ret)
# 			start = offset * limit
# 			for t in ret:
# 				start = start + 1
# 				t['ID'] = start
# 				# r = {'ID': start}
# 				# for i, items in enumerate(t):
# 				# 	r[fields[i]] = items
# 				# result.append(r)

# 			rows = hexlifyDictField(ret)
# 			self.write({
# 				"total": total,
# 				"rows": rows,
# 				"limit": limit,
# 				"offset": offset
# 			})
# 		else:
# 			columns = [
# 				{'field': 'ID', 'title': '排名'},
# 				{'field': 'id', 'title': '工会ID'},
# 				{'field': 'name', 'title': '工会名'},
# 				{'field': 'level', 'title': '工会等级'},
# 				{'field': 'members', 'title': '工会人数'},
# 				{'field': 'intro', 'title': '工会简介'},
# 				{'field': 'contrib', 'title': '总贡献值'},
# 				{'field': 'day_contrib', 'title': '当日贡献'},
# 				{'field': 'join_type', 'title': '加入类型'},
# 				{'field': 'join_level', 'title': '加入等级限制'},
# 			]

# 			columns = self.setLocalColumns(columns)
# 			self.write({
# 				'columns': columns,
# 			})
