from apilist import alimit
import time

# 从alimit继承limit配置

class Mylimit(alimit):
    def __init__(self) -> None:
        super().__init__()
        self.limitList = {}
        # 如果alimit中有新的时间粒度,要在这添加
        # 无需关心hour\minute\day与second的转换
        # 在访问后会自动去更新他们
        self.gran = ["second", "minute", "hour","day"]

    # 为IP和对应路由初始化信息并计算QPS
    def ipToroute(self,addr,route):
        self.addr = addr
        self.route = route
        # 当前日期,小时，分钟，秒
        today = time.localtime()
        self.day,self.hour,self.minute = today.tm_mday, today.tm_hour, today.tm_min
        self.second = int(time.time())

        # 若IP路由信息不存在,则创建
        self.limitList.setdefault(self.addr, {})
        self.limitList[self.addr].setdefault(self.route, {})
        self.limitList[self.addr][self.route].setdefault("count", {})
        self.limitList[self.addr][self.route].setdefault("hist", {})

        # 获取当前接口的QPS限制
        curqps = getattr(self,self.route)

        return self.qpsComp(curqps,self.limitList[self.addr][self.route],gran=self.gran)
    
    # QPS计算器
    def qpsComp(self,curqps,histqps,gran=["second"]):
        '''
        curqps  : 该路由的QPS设置
        histqps : IP对应路由的历史值
        gran    : 要计算的粒度,如天(day)\时(hour)\分(minute)\秒(second)
        '''
        # 用于存储各种状态
        dl = []
        for igran in gran:
            # 获取该粒度历史请求的时间
            if histqps["hist"].get(igran) == None:
                # 没有访问记录,添加访问记录后继续其他粒度判断
                self.updateit(gran=igran)
                dl.append(True)
                continue
            else:
                # 获取该路由对应粒度的QPS值
                sqps = str(curqps.get(igran))

                # 若无设置则放行
                if sqps == None:
                    dl.append(True)
                    continue
                
                # 若为float,表示使用的限制方式为每x粒度允许访问y次
                # 对应计算方法 
                # y/x(历史访问次数/上次访问时间到当前时间的时间差) > sqps
                # >=则表示超出QPS,< 表示为达到QPS
                if "/" in sqps:
                    # 设定的x和y
                    x,y = sqps.split("/")
                else:
                    x,y = sqps,"1"

                # 历史访问次数
                bcount = histqps["count"].get(igran,0)
                # 历史访问时间
                bhist = histqps["hist"].get(igran,0)
                # 当前访问时间
                nhist = getattr(self,igran)
                # 访问时间的间隔
                tdif = nhist - bhist
                
                # 当时差大于等于y(时差)时,初始化访问量,并退出计算
                if tdif >= int(y):
                    self.updateit(2,gran=igran)
                    dl.append(True)
                    continue

                # 否则正常计算
                try:
                    if (nqps := bcount/tdif) > int(x) / int(y):
                        self.updateit(gran=igran)
                        dl.append(False)
                        continue
                    else:
                        # 当前粒度减去一次QPS
                        self.updateit(1,gran=igran)
                        # 为其他时间粒度正常增加一次访问次数
                        [ self.updateit(gran=i) for i in gran if i!= igran ]
                        dl.append(True)
                        continue
                except ZeroDivisionError:
                    nqps = "null"
                    if tdif <= int(y):
                        if bcount >= int(x):
                            self.updateit(gran=igran)
                            dl.append(False)
                            continue
                    self.updateit(gran=igran)
                    dl.append(True)
                    continue
        # 更新历史访问时间
        self.limitList[self.addr][self.route]["hist"] = {
            "day": self.day,
            "hour": self.hour,
            "minute": self.minute,
            "second":  self.second,
            }
        return True if False not in dl else False
    
    # 为IP对应route的时间粒度增加或减少一次访问记录并更新访问时间
    def updateit(self,incre=0,gran="second"):
        '''
        incre : 0增加一次,1减少一次
        '''
        
        day = self.limitList[self.addr][self.route]["count"].get("day",0)
        hour = self.limitList[self.addr][self.route]["count"].get("hour",0)
        mine = self.limitList[self.addr][self.route]["count"].get("minute",0)
        seco = self.limitList[self.addr][self.route]["count"].get("second",0)

        if incre == 0:
            # 为IP在对应路由的访问增加一次统计
            self.limitList[self.addr][self.route]["count"] = {
                "day": day + 1 if gran in ["second", "minute", "hour","day"] and gran == "day" else day,
                "hour": hour + 1 if gran in ["second", "minute", "hour"] and gran == "hour" else hour,
                "minute": mine + 1 if gran in ["second", "minute"] and gran == "minute" else mine,
                "second": seco + 1 if gran == "second" else seco
            }

        elif incre == 1:
            # 为IP在对应路由的访问减去一次统计
            self.limitList[self.addr][self.route]["count"] = {
                "day": 1 if (xd := day - 1) <= 0 else xd,
                "hour": 1 if (xh := hour - 1) <= 0 else xh,
                "minute": 1 if (xm := mine - 1) <= 0 else xm,
                "second": 1 if (xs := seco - 1) <= 0 else xs
            }

        elif incre == 2:
            # 为IP在对应路由的访问量初始化为1
            self.limitList[self.addr][self.route]["count"] = {
                "day": 1 if gran == "day" else day,
                "hour": 1 if gran == "hour" else hour,
                "minute": 1 if gran == "minute" else mine,
                "second": 1 if gran == "second" else seco
            }
        return True

if __name__ == "__main__":
    myli = Mylimit()
    # 传入客户端的IP和你的路由名称
    print(myli.ipToroute("8.8.8.8","djt"))