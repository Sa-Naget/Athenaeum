(function () {
  var coverInput = document.querySelector('[data-cover-input]');
  if (coverInput) {
    var zone = coverInput.closest('.dropzone');
    var preview = zone.querySelector('.dropzone-preview');
    var text = zone.querySelector('.dropzone-text');
    var removeBox = document.querySelector('input[name="remove_cover"]');
    coverInput.addEventListener('change', function () {
      var file = coverInput.files[0];
      if (!file) return;
      preview.src = URL.createObjectURL(file);
      preview.hidden = false;
      text.textContent = file.name;
      if (removeBox) removeBox.checked = false;
    });
  }

  var box = document.querySelector('[data-tag-input]');
  if (box) {
    var chips = box.querySelector('.tag-chips');
    var entry = box.querySelector('input[type="text"]');
    var hidden = box.parentElement.querySelector('input[name="tags"]');
    var tags = [];

    function render() {
      chips.innerHTML = '';
      tags.forEach(function (t, i) {
        var chip = document.createElement('span');
        chip.className = 'chip';
        chip.textContent = t;
        var x = document.createElement('button');
        x.type = 'button';
        x.setAttribute('aria-label', 'Remove ' + t);
        x.textContent = '×';
        x.addEventListener('click', function () { tags.splice(i, 1); render(); });
        chip.appendChild(x);
        chips.appendChild(chip);
      });
      hidden.value = tags.join(', ');
      entry.placeholder = tags.length ? '' : 'Manga, Manhwa, Manhua';
    }

    function add(raw) {
      var t = raw.trim();
      if (t && tags.indexOf(t) === -1) tags.push(t);
      render();
    }

    hidden.value.split(',').forEach(add);

    entry.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        add(entry.value);
        entry.value = '';
      } else if (e.key === 'Backspace' && !entry.value && tags.length) {
        tags.pop();
        render();
      }
    });
    entry.addEventListener('input', function () {
      if (entry.value.indexOf(',') !== -1) {
        var parts = entry.value.split(',');
        entry.value = parts.pop();
        parts.forEach(add);
      }
    });
    entry.addEventListener('blur', function () { add(entry.value); entry.value = ''; });
    entry.closest('form').addEventListener('submit', function () { add(entry.value); entry.value = ''; });
    box.addEventListener('click', function () { entry.focus(); });
  }
})();
