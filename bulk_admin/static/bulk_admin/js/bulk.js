(function($) {
    'use strict';

    $.fn.bulkUpload = function(opts) {
        var options = $.extend({}, $.fn.bulkUpload.defaults, opts);
        var $this = $(this);
        var submitted = false;

        $this.click(function() {
            var field = $this.data('field');

            var $form = $('<form>')
                .attr('method', 'POST')
                .attr('action', '')
                .attr('enctype', 'multipart/form-data');

            var $fileInput = $('<input>')
                .attr('type', 'file')
                .attr('name', options.prefix + '-' + field)
                .attr('multiple', 'multiple');
            $form.append($fileInput);

            var $csrfInput = $('<input>')
                .attr('type', 'text')
                .attr('name', options.csrfTokenName)
                .attr('value', options.csrfToken);
            $form.append($csrfInput);

            var $totalFormCountInput = $('<input>')
                .attr('type', 'number')
                .attr('name', options.prefix + '-' + 'TOTAL_FORMS');
            $form.append($totalFormCountInput);

            var $initialFormCountInput = $('<input>')
                .attr('type', 'number')
                .attr('name', options.prefix + '-' + 'INITIAL_FORMS')
                .attr('value', '0');
            $form.append($initialFormCountInput);

            if (options.isPopup) {
                var $isPopupInput = $('<input>')
                    .attr('type', 'number')
                    .attr('name', options.isPopupName)
                    .attr('value', '1');
                $form.append($isPopupInput);
            }

            if (options.toField) {
                var $toFieldInput = $('<input>')
                    .attr('type', 'text')
                    .attr('name', options.toFieldName)
                    .attr('value', options.toField);
                $form.append($toFieldInput);
            }

            if (options.continue) {
                var $continueField = $('<input>')
                    .attr('type', 'text')
                    .attr('name', options.continueName)
                    .attr('value', 'on');
                $form.append($continueField);
            }

            $fileInput.change(function() {
                if (submitted) {
                    return;
                }

                if (options.submittingMessage) {
                    $this.text(options.submittingMessage);
                }

                $totalFormCountInput.attr('value', this.files.length);

                // HTML spec updates require forms to be attached to document 
                // body before submission.
                $(document.body).append($form);
                $form.submit();

                submitted = true;
            });

            $fileInput.trigger('click');
        });
    };

    $.fn.bulkUpload.defaults = {
        prefix: 'form',
        csrfTokenName: 'csrfmiddlewaretoken',
        isPopupName: '_popup',
        isPopup: false,
        toFieldName: '_to_field',
        toField: '',
        continueName: '_continue',
        continue: true,
        submittingMessage: 'Files are being uploaded...',
    };

})(django.jQuery);
