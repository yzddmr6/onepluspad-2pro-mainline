// SPDX-License-Identifier: GPL-2.0-or-later
//
// GNOME Shell 50 KeyboardManager.maybeHandleEvent() (js/ui/keyboard.js:1153)
// passes the result of global.stage.get_event_actor() to
// keyboardBox.contains() without a null check. When a touch sequence ends,
// Clutter clears the sprite's current actor and only then emits the LEAVE
// crossing event, so the unlock dialog, modal dialogs and popup-menu grabs
// that call maybeHandleEvent() from their captured-event handlers raise
// "Argument descendant may not be null" once per touch release.
//
// With no actor there is nothing to forward to the on-screen keyboard, so the
// event is reported as not handled; every other event runs the unchanged
// original method. GNOME Shell 51 (commit 5e5b0f49d35a) removed the method,
// and shell-version ["50"] keeps this extension from loading there.
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {KeyboardManager} from 'resource:///org/gnome/shell/ui/keyboard.js';

export default class OskGuardExtension extends Extension {
    enable() {
        const original = KeyboardManager.prototype.maybeHandleEvent;
        this._original = original;
        KeyboardManager.prototype.maybeHandleEvent = function (event) {
            if (!global.stage.get_event_actor(event))
                return false;
            return original.call(this, event);
        };
    }

    disable() {
        KeyboardManager.prototype.maybeHandleEvent = this._original;
        this._original = null;
    }
}
