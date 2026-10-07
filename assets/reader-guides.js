(function () {
  document.querySelectorAll('[data-copy-questions]').forEach(function (button) {
    button.hidden = false;
    button.addEventListener('click', function () {
      var box = button.closest('[data-question-kit]');
      var text = Array.from(box.querySelectorAll('[data-question-text] li')).map(function (item) { return '• ' + item.textContent.trim(); }).join('\n');
      var status = box.querySelector('[role="status"]');
      if (!navigator.clipboard) { status.textContent = 'Select the questions below and copy them into your notes.'; return; }
      navigator.clipboard.writeText(text).then(function () {
        status.textContent = 'Questions copied. Add the answers to your own notes.';
      }).catch(function () { status.textContent = 'Copy was blocked. Select the questions below and copy them manually.'; });
    });
  });
})();
