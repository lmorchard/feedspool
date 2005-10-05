/*
    miniagg outline UI implementation
*/

function init() {
    // Debounce the init call
    if (arguments.callee.done) return;
    arguments.callee.done = true;

    // Build all the list outline controls.
    var lis = document.getElementsByTagName('li')
    for (var i=0; i<lis.length; i++) {
        var li = lis[i];
        var cn = li.className;

        if (/feed/.test(cn) || /entry/.test(cn)) {
            insertLinkShortcut(li);
            if (/feed/.test(cn)) insertToggleAll(li);
            insertOutlineHandle(li);
        }

    }
}

function insertToggleAll(li) {
    var button = document.createElement("span");
    button.appendChild(document.createTextNode("show all"));
    button.className = "control button";
    button.onclick = function() { return toggleChildren(li); }
    li.insertBefore(button, li.firstChild);
}

function insertLinkShortcut(li) {
    var links = li.getElementsByTagName('a');
    if (links.length > 0) {
        var link = document.createElement("a");
        link.className = "link button";
        link.href      = links[0].href;
        link.target    = "_new";
        link.appendChild(document.createTextNode("link"));
        li.insertBefore(link, li.firstChild);
    }
}

function insertOutlineHandle(li) {
    li.insertBefore(buildHandle(li, 'handle_alt'), li.firstChild);
    li.insertBefore(buildHandle(li, 'handle'), li.firstChild);
}

function buildHandle(li, cn) {
    var handle = document.createElement("span");
    handle.appendChild(document.createTextNode("\u00a0\u00a0"));
    handle.className = cn;
    handle.onclick = function() { return toggleOutline(li); }
    return handle;
}

function toggleChildren(parent_li) {
    var uls = parent_li.getElementsByTagName('ul');
    for (var i=0; i<uls.length; i++) {
        var lis = uls[i].getElementsByTagName('li');
        for (var j=0; j<lis.length; j++)
            toggleOutline(lis[j]);
    }
}

function toggleOutline(li) {
    var cn = li.className;
    if (/ expanded/.test(cn)) {
        cn = cn.replace('expanded', 'collapsed');
    } else if (/ collapsed/.test(cn)) {
        cn = cn.replace('collapsed', 'expanded');
    } else {
        cn += ' expanded';
    }
    li.className = cn;
}

/*
    Smarter onload handling.
    See: http://dean.edwards.name/weblog/2005/09/busted/
*/

/* for Mozilla */
if (document.addEventListener) {
    document.addEventListener("DOMContentLoaded", init, null);
}

/* for Internet Explorer */   
/*@cc_on @*/
/*@if (@_win32)
document.write("<script defer src=js/ie_onload.js><"+"/script>");
/*@end @*/

/* for other browsers */
window.onload = init;

