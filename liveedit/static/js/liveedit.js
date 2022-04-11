(function() {
    var liveedit_context = {};

    function liveedit_close_panel() {
        if(liveedit_context.edit_panel) {
            var panel = liveedit_context.edit_panel;
            panel.style.bottom = '-60vh';
            liveedit_context.edit_panel = null;
            setTimeout(function() {
                panel.remove();
            }, 500);
        }
    }

    document.querySelectorAll('*[data-liveedit]').forEach(function(el) {
        var data = JSON.parse(el.getAttribute('data-liveedit'));

        var bar = document.createElement('div');
        bar.classList.add('liveedit-bar');
        bar.setAttribute('id', 'le-' + data.id);

        function submitAction(action) {
            var form = document.createElement('form');
            form.style.display = 'none';
            form.setAttribute('method', 'post');
            form.setAttribute('action', '/__liveedit__/action/');

            data['action'] = action;
            data['page_url'] = window.location.href;
            Object.keys(data).forEach(function(k) {
                var inp = document.createElement('input');
                inp.setAttribute('type', 'hidden');
                inp.setAttribute('name', k);
                inp.setAttribute('value', data[k]);
                form.appendChild(inp);
            });

            document.body.appendChild(form);
            form.submit();
        }

        var btn = document.createElement('button');
        btn.appendChild(document.createTextNode('🡄'));
        btn.addEventListener('click', function(ev) {
            ev.preventDefault();
            submitAction('move_up');
        });
        bar.appendChild(btn);

        var btn = document.createElement('button');
        btn.appendChild(document.createTextNode('🡆'));
        btn.addEventListener('click', function(ev) {
            ev.preventDefault();
            submitAction('move_down');
        });
        bar.appendChild(btn);

        function loadEditPanel(url, panel_title) {
            if(liveedit_context.edit_panel) return; //panel already open

            var con = document.createElement('div');
            con.classList.add('liveedit-panel');
            liveedit_context.edit_panel = con;
            setTimeout(function() {
                con.style.bottom = 0;
            }, 50);

            var topbar = document.createElement('div');
            topbar.classList.add('liveedit-topbar');

            var title = document.createElement('div');
            
            title.appendChild(document.createTextNode(panel_title));
            title.classList.add('liveedit-title');
            topbar.appendChild(title);

            var close = document.createElement('div');
            close.style.cursor = "pointer";
            close.innerHTML = '<svg id="icon-cross" viewBox="0 0 16 16"><path d="M13.313 11.313c0 0.219-0.094 0.438-0.25 0.594l-1.219 1.219c-0.156 0.156-0.375 0.25-0.625 0.25-0.219 0-0.438-0.094-0.594-0.25l-2.625-2.625-2.625 2.625c-0.156 0.156-0.375 0.25-0.594 0.25-0.25 0-0.469-0.094-0.625-0.25l-1.219-1.219c-0.156-0.156-0.25-0.375-0.25-0.594 0-0.25 0.094-0.438 0.25-0.625l2.625-2.625-2.625-2.625c-0.156-0.156-0.25-0.375-0.25-0.594 0-0.25 0.094-0.438 0.25-0.625l1.219-1.188c0.156-0.188 0.375-0.25 0.625-0.25 0.219 0 0.438 0.063 0.594 0.25l2.625 2.625 2.625-2.625c0.156-0.188 0.375-0.25 0.594-0.25 0.25 0 0.469 0.063 0.625 0.25l1.219 1.188c0.156 0.188 0.25 0.375 0.25 0.625 0 0.219-0.094 0.438-0.25 0.594l-2.625 2.625 2.625 2.625c0.156 0.188 0.25 0.375 0.25 0.625z"></path></svg>';
            close.style.float = 'right';
            close.addEventListener('click', liveedit_close_panel);
            topbar.appendChild(close);
            con.appendChild(topbar);

            var iframe = document.createElement('iframe');
            iframe.setAttribute('src', url);
            con.appendChild(iframe);
            

            /*
            let shadow = con.attachShadow({mode: 'open'});

            fetch('/liveedit/test/')
                .then(function(response) {
                    return response.text();
                }).then(function(text) {
                    shadow.innerHTML = text;
                    Array.from(shadow.querySelectorAll("script")).forEach( oldScript => {
                        const newScript = document.createElement("script");
                        Array.from(oldScript.attributes)
                        .forEach( attr => newScript.setAttribute(attr.name, attr.value) );
                        newScript.appendChild(document.createTextNode(oldScript.innerHTML));
                        oldScript.parentNode.replaceChild(newScript, oldScript);
                    });
                });
            */

            document.body.appendChild(con);
        }

        btn = document.createElement('button');
        btn.appendChild(document.createTextNode('Edit'));
        btn.addEventListener('click', function(ev) {
            ev.preventDefault();
            loadEditPanel(
                '/__liveedit__/edit-block/?id=' + encodeURIComponent(data.id) + 
                '&content_type_id=' + encodeURIComponent(data.content_type_id) +
                '&object_id=' + encodeURIComponent(data.object_id) +
                '&object_field=' + encodeURIComponent(data.object_field),
                "Edit " + data.block_type.replace(/_/g, ' '),
            );
        });
        bar.appendChild(btn);

        var btn = document.createElement('button');
        btn.appendChild(document.createTextNode('＋'));
        btn.addEventListener('click', function(ev) {
            ev.preventDefault();
            loadEditPanel(
                '/__liveedit__/append-block/?id=' + encodeURIComponent(data.id) + 
                '&content_type_id=' + encodeURIComponent(data.content_type_id) +
                '&object_id=' + encodeURIComponent(data.object_id) +
                '&object_field=' + encodeURIComponent(data.object_field),
                "Insert new"
            );
        });
        bar.appendChild(btn);


        el.insertAdjacentElement('afterbegin', bar);
        el.setAttribute('data-liveedit-active', true);
    });

    window.addEventListener("message", function(event) {
        // is this sufficient?
        if(event.origin != window.origin) return;

        if(event.data && event.data.action=="reload") {
            if(liveedit_context.edit_panel) {
                liveedit_context.edit_panel.style.bottom = '-60vh';
            }
            window.location.reload();
        } else if(event.data && event.data.action=="close_panel") {
            liveedit_close_panel();
        }

    }, false);

    if(window._live_edit_draft_url) {
        var notice = document.createElement('div');
        notice.classList.add('liveedit-notice');
        notice.appendChild(document.createTextNode("There is an unpublished draft of this page."));

        var btn = document.createElement('a');
        btn.setAttribute('href', window._live_edit_draft_url)
        btn.appendChild(document.createTextNode("View"));
        notice.appendChild(btn);

        document.body.appendChild(notice);
    }
})();
