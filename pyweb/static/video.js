let videoItems;
let current;
const player = $('.video-player');
const videoName = $('.video-name', player);
const video = $('video', player);
video.addEventListener('ended', playNext, false);
$('.video-prev', player).addEventListener('click', e => {
  playOffset(-1);
}, false);
$('.video-next', player).addEventListener('click', playNext, false);
$('.video-close', player).addEventListener('click', e => {
  playItem(null);
}, false);
$('.video-play').addEventListener('click', playAll, false);
document.addEventListener('click', e => {
  const { target } = e;
  if (target.classList.contains('btn-play')) {
    const currentEl = target.parentNode;
    const item = videoItems.find(({ el }) => el === currentEl);
    if (item) playItem(item);
  }
}, false);
document.addEventListener('DOMContentLoaded', e => {
  videoItems = Array.from($$('.file-video>.link'), a => ({
    name: a.textContent,
    url: a.href,
    el: a.parentNode,
  }));
}, false);

function $(selector, context) {
  return (context || document).querySelector(selector);
}

function $$(selector, context) {
  return (context || document).querySelectorAll(selector);
}

function playItem(item) {
  current = item;
  if (item) {
    videoName.textContent = item.name || 'Noname';
    player.classList.add('active');
    video.src = item.url;
    video.play();
  } else {
    videoName.textContent = '';
    player.classList.remove('active');
    video.src = '';
  }
}

function playOffset(offset) {
  const index = videoItems.indexOf(current);
  if (index >= 0) playItem(videoItems[index + offset]);
}

function playNext() {
  playOffset(1);
}

function playAll() {
  playItem(videoItems[0]);
}
