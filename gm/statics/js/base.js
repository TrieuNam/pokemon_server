// sleep函数，暂停程序，1000ms
function sleep(sleepTime) {
	var start = new Date().getTime();
	while (true) {
		if (new Date().getTime() - start > sleepTime) {
			break;
		};
	};
};

// WebSocket
function BaseWebSocket(url) {
    if ("WebSocket" in window) {
    	/*
    	发送消息
		this.ws.onopen = function() {
			this.send("hello, world")
		}
		接收消息
		this.ws.onmessage = function(MessageEvent) {
			console.log(MessageEvent)
		}
    	*/
    	this.url = 'ws://' + url;
        this.ws = new WebSocket(this.url);
        this.readyState = function() {
        	/*
			0 - 表示连接尚未建立。
			1 - 表示连接已建立，可以进行通信。
			2 - 表示连接正在进行关闭。
			3 - 表示连接已经关闭或者连接不能打开。
        	*/
        	return this.ws.readyState;
        };
        this.close = function() {
        	this.ws.close();
        };
        this.ws.onerror = function(err) {
            console.log(this.url, ":", err);
        };
        this.ws.onclose = function() {
            console.log(this.url, ":closed")
        };
    } else {
    	alert("不支持WebSocket");
    }
};

// 去除string首尾空格
String.prototype.trim = function() {
    return this.replace(/(^\s*)|(\s*$)/g, "");
}

// 请求异常处理
$(document).ajaxError(function(event, xhr, options, exc) {
    console.log(event, xhr, options, exc);
    if (xhr.status === 504) {
        alert("Sorry, You don't have enough permissions, Please contact the administrator");
    } else {
        alert("Error: " + xhr.status + "  " + xhr.statusText);
    }
});

// 当ajax请求开始时
$(document).ajaxStart(function(){
    console.log('ajax request start---');
    $("#ajax-loading").modal("show");
});

// 当ajax请求结束时
$(document).ajaxStop(function(){
    console.log('ajax request end---');
    changeCopyrightPosition();
    $("#ajax-loading").modal("hide");
});

// framework language
const userLocale = $('footer').attr('language')

// copyright
function changeCopyrightPosition() {
    let w = $(window).height();
    let b = $('.main').height() + 75;
    console.log(w, b)
    if (b >= w-16) {
        $('#copyright').css('margin-top', 0)
    } else {
        $('#copyright').css('margin-top', w - b - 16 + 'px')
    }
    $('#copyright').css('display', 'block')
}

function prettyJSON(s) {
    let n = "";
    let cl = 0;
    let cr = 0;
    let sj = "  ";

    for (let i=0; i<s.length; i++) {

        if (s[i] === "{" || s[i] === "[") {
            cl += 1;
            n += s[i] + "\n";
            for (let c=0; c<cl-cr; c++) {
                n += sj;
            }
        }
        else if (s[i] === ",") {
            n += s[i] + "\n";
            for (let c=0; c<cl-cr; c++) {
                n += sj;
            }
        }
        else if (s[i] === "]" || s[i] === "}") {
            cr += 1;
            n += "\n"
            for (let c=0; c<cl-cr; c++) {
                n += sj;
            }
            n += s[i];
        }
        else {
            n += s[i];
        }
    }
    return n;
}

function paddingInputDate($ele, days=0) {
    let n = new Date();
    let n_s = n.getTime();
    n.setTime(n_s - 1000*60*60*24*days);
    let d = n.getDate();
    let m = n.getMonth() + 1;
    if (m < 10) {
        m = "0" + m;
    }
    if (d < 10) {
        d = "0" + d;
    }
    let f = n.getFullYear() + '-' + m + '-' + d;
    $ele.val(f)
}