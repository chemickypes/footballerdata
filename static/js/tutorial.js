/* ============================================================
   Tutorial Interattivo Spotlight — fanta-lab
   Zero-dependency walkthrough engine (vanilla JS, IIFE module).
   ============================================================ */

window.FantaTour = (function () {
    'use strict';

    // Placeholder steps for engine verification (Task 3 replaces this with the real 7-step tour).
    var STEPS = [
        { selector: 'body', title: 'Passo 1 (placeholder)', text: 'Testo placeholder 1.' },
        { selector: 'body', title: 'Passo 2 (placeholder)', text: 'Testo placeholder 2.' }
    ];

    var STORAGE_KEY = 'fanta_tour_done';
    var currentIndex = -1;
    var overlayEls = [];
    var tooltipEl = null;
    var resizeHandler = null;

    function _clearOverlay() {
        overlayEls.forEach(function (el) {
            if (el && el.parentNode) el.parentNode.removeChild(el);
        });
        overlayEls = [];
        if (tooltipEl && tooltipEl.parentNode) {
            tooltipEl.parentNode.removeChild(tooltipEl);
        }
        tooltipEl = null;
    }

    function _computeOverlayRects(targetEl) {
        var rect = targetEl.getBoundingClientRect();
        var vw = window.innerWidth;
        var vh = window.innerHeight;
        return {
            top: { top: 0, left: 0, width: vw, height: Math.max(0, rect.top) },
            bottom: { top: rect.bottom, left: 0, width: vw, height: Math.max(0, vh - rect.bottom) },
            left: { top: rect.top, left: 0, width: Math.max(0, rect.left), height: rect.height },
            right: { top: rect.top, left: rect.right, width: Math.max(0, vw - rect.right), height: rect.height },
            highlight: { top: rect.top - 4, left: rect.left - 4, width: rect.width + 8, height: rect.height + 8 }
        };
    }

    function _applyRectStyle(el, rectDef) {
        el.style.top = rectDef.top + 'px';
        el.style.left = rectDef.left + 'px';
        el.style.width = rectDef.width + 'px';
        el.style.height = rectDef.height + 'px';
    }

    function _renderOverlay(targetEl) {
        var rects = _computeOverlayRects(targetEl);
        var keys = ['top', 'bottom', 'left', 'right'];
        keys.forEach(function (key) {
            var el = document.createElement('div');
            el.className = 'tour-overlay-rect';
            _applyRectStyle(el, rects[key]);
            document.body.appendChild(el);
            overlayEls.push(el);
        });
        var highlightEl = document.createElement('div');
        highlightEl.className = 'tour-overlay-highlight';
        _applyRectStyle(highlightEl, rects.highlight);
        document.body.appendChild(highlightEl);
        overlayEls.push(highlightEl);
    }

    function _positionTooltip(targetEl, step) {
        var rect = targetEl.getBoundingClientRect();
        var vh = window.innerHeight;
        var spaceBelow = vh - rect.bottom;
        var spaceAbove = rect.top;
        var placeBelow = spaceBelow >= 160 || spaceBelow >= spaceAbove;

        tooltipEl = document.createElement('div');
        tooltipEl.className = 'tour-tooltip';

        var skipBtn = document.createElement('button');
        skipBtn.className = 'tour-btn-skip';
        skipBtn.textContent = 'Salta Tutorial ✕';
        skipBtn.onclick = function () { FantaTour.skip(); };
        tooltipEl.appendChild(skipBtn);

        var titleEl = document.createElement('div');
        titleEl.className = 'tour-tooltip-title';
        titleEl.textContent = step.title;
        tooltipEl.appendChild(titleEl);

        var textEl = document.createElement('div');
        textEl.className = 'tour-tooltip-text';
        textEl.textContent = step.text;
        tooltipEl.appendChild(textEl);

        var progressEl = document.createElement('div');
        progressEl.className = 'tour-tooltip-progress';
        progressEl.textContent = 'Passo ' + (currentIndex + 1) + ' di ' + STEPS.length;
        tooltipEl.appendChild(progressEl);

        var actionsEl = document.createElement('div');
        actionsEl.className = 'tour-tooltip-actions';

        var prevBtn = document.createElement('button');
        prevBtn.className = 'tour-btn tour-btn-secondary';
        prevBtn.textContent = 'Indietro';
        prevBtn.disabled = currentIndex === 0;
        prevBtn.onclick = function () { FantaTour.prev(); };
        actionsEl.appendChild(prevBtn);

        var nextBtn = document.createElement('button');
        nextBtn.className = 'tour-btn tour-btn-primary';
        nextBtn.textContent = (currentIndex === STEPS.length - 1) ? 'Fine' : 'Avanti';
        nextBtn.onclick = function () { FantaTour.next(); };
        actionsEl.appendChild(nextBtn);

        tooltipEl.appendChild(actionsEl);

        var arrow = document.createElement('div');
        arrow.className = 'tour-tooltip-arrow ' + (placeBelow ? 'tour-tooltip-arrow-top' : 'tour-tooltip-arrow-bottom');
        tooltipEl.appendChild(arrow);

        document.body.appendChild(tooltipEl);

        // Measure after insertion to get real tooltip dimensions.
        var tw = tooltipEl.offsetWidth;
        var th = tooltipEl.offsetHeight;
        var left = Math.min(Math.max(8, rect.left + rect.width / 2 - tw / 2), window.innerWidth - tw - 8);
        var top = placeBelow ? (rect.bottom + 14) : (rect.top - th - 14);
        top = Math.max(8, Math.min(top, window.innerHeight - th - 8));

        tooltipEl.style.left = left + 'px';
        tooltipEl.style.top = top + 'px';
    }

    function _renderStep(index) {
        _clearOverlay();
        if (index < 0 || index >= STEPS.length) return;
        var step = STEPS[index];
        var targetEl = document.querySelector(step.selector);
        if (!targetEl) {
            console.warn('[FantaTour] Target not found for step ' + index + ' (selector: ' + step.selector + '), skipping.');
            if (index < currentIndex || currentIndex === -1) {
                currentIndex = index;
                _advanceSkippingMissing(1);
            } else {
                currentIndex = index;
                _advanceSkippingMissing(-1);
            }
            return;
        }
        currentIndex = index;
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        _renderOverlay(targetEl);
        _positionTooltip(targetEl, step);
    }

    function _advanceSkippingMissing(direction) {
        var nextIndex = currentIndex + direction;
        if (nextIndex < 0) { _teardown(); return; }
        if (nextIndex >= STEPS.length) { _finish(); return; }
        _renderStep(nextIndex);
    }

    function _teardown() {
        _clearOverlay();
        currentIndex = -1;
        if (resizeHandler) {
            window.removeEventListener('resize', resizeHandler);
            window.removeEventListener('scroll', resizeHandler, true);
            resizeHandler = null;
        }
    }

    function _finish() {
        localStorage.setItem(STORAGE_KEY, 'true');
        _teardown();
    }

    function start() {
        _teardown();
        currentIndex = 0;
        _renderStep(0);
        resizeHandler = function () {
            if (currentIndex >= 0 && currentIndex < STEPS.length) {
                var step = STEPS[currentIndex];
                var targetEl = document.querySelector(step.selector);
                if (targetEl) {
                    _clearOverlay();
                    _renderOverlay(targetEl);
                    _positionTooltip(targetEl, step);
                }
            }
        };
        window.addEventListener('resize', resizeHandler);
        window.addEventListener('scroll', resizeHandler, true);
    }

    function next() {
        if (currentIndex === STEPS.length - 1) {
            _finish();
            return;
        }
        _renderStep(currentIndex + 1);
    }

    function prev() {
        if (currentIndex <= 0) return;
        _renderStep(currentIndex - 1);
    }

    function skip() {
        localStorage.setItem(STORAGE_KEY, 'true');
        _teardown();
    }

    function maybeAutoStart() {
        if (localStorage.getItem(STORAGE_KEY) === 'true') return;
        setTimeout(function () { start(); }, 600);
    }

    return {
        start: start,
        next: next,
        prev: prev,
        skip: skip,
        maybeAutoStart: maybeAutoStart
    };
})();
