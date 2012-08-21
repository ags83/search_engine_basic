
function downloadUrl(url, type, data, callback) {
	var status = -1;
	var request = new XMLHttpRequest();
	
	request.onreadystatechange = function() {
		if (request.readyState == 4) {
			status = request.status;
			if (status == 200) {		
				callback(request.responseText);
				request.onreadystatechange = function() {};

			}
		}
	}	
	request.open(type, url, true);
	if (type == "POST") {
		request.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
		request.setRequestHeader("Content-length", data.length);
		request.setRequestHeader("Connection", "close");
	}
	request.send(data);
};



function runMagic(e){
	var terms = document.getElementById("search_input").value + String.fromCharCode(e.which);
	downloadUrl("/suggestions", "POST", "input=" + terms.toLowerCase(), completed);
}

function updateInput(){
	var x = document.search_form.suggestions.selectedIndex;
	var y = document.search_form.suggestions.options;
	
	document.getElementById("search_input").value = y[x].text
}

function completed(responseText){
	var suggestions = JSON.parse(responseText);
	document.search_form.suggestions.options.length=0
	for (a in suggestions['suggestions']) {
		document.search_form.suggestions.options[a]=new Option(suggestions['suggestions'][a], suggestions['suggestions'][a], false, false)
	}
}

function downloadScript(url) {
	var script = document.createElement('script');
	script.src = url;
	document.body.appendChild(script);
}