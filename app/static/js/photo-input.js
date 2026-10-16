(function (root) {
  const mimeByExtension = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp' };
  function normalize(file) {
    const type = file.type || mimeByExtension[(file.name || '').split('.').pop().toLowerCase()];
    if (!Object.values(mimeByExtension).includes(type)) return null;
    return file.type ? file : new File([file], file.name, { type, lastModified: file.lastModified });
  }
  function extract(transfer) {
    const files = Array.from(transfer?.files || []);
    if (files.length) return files;
    return Array.from(transfer?.items || []).filter(item => item.kind === 'file')
      .map(item => item.getAsFile()).filter(Boolean);
  }
  root.PhotoInput = { normalize, extract };
  if (typeof module !== 'undefined') module.exports = root.PhotoInput;
})(globalThis);
