/* Progressively enhance the full static archive with shareable topic filters. */
(() => {
  'use strict';
  const navigation = document.getElementById('blog-topics');
  const status = document.getElementById('blog-topic-status');
  if (!navigation || !status) return;

  const links = Array.from(navigation.querySelectorAll('a[data-blog-topic]'));
  const posts = Array.from(document.querySelectorAll('.post-preview[data-topics]'));
  const labels = new Map(links.map(link => [link.dataset.blogTopic, link.dataset.topicLabel]));

  function currentTopic() {
    const requested = new URL(window.location.href).searchParams.get('tag') || '';
    return labels.has(requested) ? requested : '';
  }

  function render() {
    const topic = currentTopic();
    let count = 0;
    for (const post of posts) {
      const show = !topic || post.dataset.topics.split(' ').includes(topic);
      post.hidden = !show;
      if (show) count++;
    }
    for (const link of links) {
      if (link.dataset.blogTopic === topic) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    }
    status.textContent = `${count} ${count === 1 ? 'post' : 'posts'}${topic ? ` · ${labels.get(topic)}` : ''}`;
  }

  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a[data-blog-topic]');
    if (!link || !labels.has(link.dataset.blogTopic) || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;

    event.preventDefault();
    const url = new URL(window.location.href);
    if (link.dataset.blogTopic) url.searchParams.set('tag', link.dataset.blogTopic);
    else url.searchParams.delete('tag');
    url.hash = '';
    if (url.href !== window.location.href) window.history.pushState(null, '', url);
    render();

    // A card can disappear after its tag is selected. Move focus to the
    // matching filter so keyboard users retain a visible place in the page.
    if (!navigation.contains(link)) {
      const active = links.find(item => item.dataset.blogTopic === link.dataset.blogTopic);
      active.focus({ preventScroll: true });
      navigation.scrollIntoView({ block: 'start' });
    }
  });

  window.addEventListener('popstate', render);
  window.addEventListener('pageshow', render);
  render();
})();
