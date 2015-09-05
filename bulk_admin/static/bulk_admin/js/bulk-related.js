(function($) {
    'use strict';

    function windowname_to_id(text) {
        text = text.replace(/__dot__/g, '.');
        text = text.replace(/__dash__/g, '-');
        return text;
    }

    function dismissAddRelatedObjectPopup(openerWindow, newIds, newReprs) {
        var name = windowname_to_id(window.name);
        var elem = openerWindow.document.getElementById(name);
        if (elem) {
            var elemName = elem.nodeName.toUpperCase();
            if (elemName === 'SELECT') {
                for (var i = 0; i < newIds.length; i++) {
                    elem.options[elem.options.length] = new Option(newReprs[i], newIds[i], true, true);
                }
            } else if (elemName === 'INPUT') {
                if (elem.className.indexOf('vManyToManyRawIdAdminField') !== -1 && elem.value) {
                    elem.value += ',' + newIds.join(',');
                } else {
                    elem.value = newIds.join(',');
                }
            }
            // Trigger a change event to update related links if required.
            openerWindow.django.jQuery(elem).trigger('change');
        } else {
            var toId = name + "_to";

            for (var i = 0; i < newIds.length; i++) {
                openerWindow.SelectBox.add_to_cache(toId, new Option(newRepr, newId));
                openerWindow.SelectBox.redisplay(toId);
            }
        }
        window.close();
    }

    window.dismissAddRelatedObjectPopup = dismissAddRelatedObjectPopup;

})();
