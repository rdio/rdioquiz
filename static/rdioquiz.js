var cb = {};
var rdio = null;
var points = 0;
var score = 0;
cb.ready = function() {
  rdio = $('#api_swf').get(0);
  rdio.rdio_play(track);
  rdio.rdio_setRepeat(1); // track repeat
}
cb.playStateChanged = function(playState) {
  if (playState == 1 && state == 'loading') {
    setState('playing');
  }
}
cb.positionChanged = function(position) {
  if (position < 30) {
    points = Math.floor(30 - position);
    $('#points').text(points);
  } else if (state == 'playing') {
    // FAIL
    rdio.rdio_stop();
    setState('timeout');
    addScore(-30);
  }
}


$(document).ready(function() {
  var flashvars = {
    'playbackToken': playbackToken,
    'domain': domain,
    'listener': 'cb'
    };
  var params = {
    'allowScriptAccess': 'always'
  };
  var attributes = {};
  swfobject.embedSWF(api_swf, 'api_swf', 1, 1, '9.0.0', 'expressInstall.swf', flashvars, params, attributes);

  $('#start').click(function(){ start_round(); });

  // set up the list of albums' event handler
  $('#options li').each(function(i) {
    $('div.clickable', this).click(function() {
      $('.albums').addClass('roundover');
      $(playing_album['element']).addClass('correct');
      if (state != 'playing') return;
      if (albums_in_play[i]['key'] == playing_album['key']) {
        setState('won');
        addScore(points);
      } else {
        setState('lost');
        addScore(-30);
        rdio.rdio_stop();
      }
    })
  });

  setState('initial');
})

var albums_in_play = null;
var playing_album = null;

var state = null;
// update the UI to the state
// valid states are: initial, loading, playing, won, lost, timeout
function setState(name) {
  state = name;
  
  if (name == 'initial') {
    $('#options,#loading,#points_container').hide();
    $('#instructions').show();
    $('#start').show().text('Ready? Start Playing!');
  } else if (name == 'loading') {
    $('#options,#start,#points_container,#instructions').hide();
    $('#loading').show();
  } else if (name == 'playing') {
    $('#loading,#start,#instructions').hide();
    $('.albums').removeClass('roundover');
    $('.albums li').removeClass('correct');
    $('#options,#points_container').show();
  } else if (name == 'won') {
    $('#loading,#points_container').hide();
    $('#start').text('Right! Play Again?').show();
    $('#start').removeClass('wrong');
  } else if (name == 'lost') {
    $('#loading,#points_container').hide();
    $('#start').addClass('wrong');
    $('#start').text('Wrong! Play Again?').show();
  } else if (name == 'timeout') {
    $('#loading,#points_container').hide();
    $('#start').addClass('wrong');
    $('#start').text('Time\'s Up! Play Again?').show();
  }
}

function page(name) {
  $('div.page').hide();
  $('#'+name).show();
}

function addScore(v) {
  score = score + v;
  $('#score').text(score);
}

function start_round() {
  // pick three albums
  albums_in_play = floyd(albums, 3);
  // choose one of them to play
  playing_album = albums_in_play[randint(albums_in_play.length)];

  // set up the list of albums
  $('#options li').each(function(i) {
    var album = albums_in_play[i];
    album.element = this;
    $('img.art', this).attr('src', album['icon']);
    $('.artistname', this).text(album['artist']);
    $('.listen a', this).attr('href', album['shortUrl']);
  });

  $('#points').text("30");

  setState('loading');
  
  // choose a track off the album to play
  var playing_track = playing_album.tracks[randint(playing_album.tracks.length)];
  // play it
  rdio.rdio_play(playing_track);
}

function randint(range) {
  return Math.floor(Math.random()*range);
}

// choose m random items
function floyd(items, m) {
  var res = [];
  var n = items.length;

  for (var i=n-m; i<n; i++) {
    var pos = randint(i+1);
    var item = items[pos];
    if (res.indexOf(item) == -1) {
      res.push(item);
    } else {
      res.push(items[i]);
    }
  }
  return res;
}
