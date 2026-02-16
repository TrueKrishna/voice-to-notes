/**
 * Voice Infrastructure Portal — V2 Application
 * Alpine.js components for live dashboard, notes, tasks, uploads.
 */

document.addEventListener('alpine:init', function() {
    console.log('L1 V2 initializing...');

    // ========================================================================
    // LIVE SYSTEM STATUS — Polls /v2/api/system-status every 3s
    // ========================================================================
    Alpine.data('liveSystem', function(initial) {
        return {
            watcher: initial.watcher || {},
            stats: initial.stats || {},
            apiKeys: initial.api_keys || {},
            recentActivity: initial.recent_activity || [],
            failedFiles: initial.failed_files || [],
            ingestFiles: initial.ingest_files || [],
            config: initial.config || {},
            lastPoll: null,
            pollInterval: null,
            pollError: false,
            activityExpanded: true,

            init: function() {
                var self = this;
                self.lastPoll = new Date();
                self.pollInterval = setInterval(function() { self.poll(); }, 3000);
            },
            
            destroy: function() {
                if (this.pollInterval) clearInterval(this.pollInterval);
            },

            poll: function() {
                var self = this;
                fetch('/v2/api/system-status')
                    .then(function(res) { return res.json(); })
                    .then(function(data) {
                        self.watcher = data.watcher || {};
                        self.stats = data.stats || {};
                        self.apiKeys = data.api_keys || {};
                        self.recentActivity = data.recent_activity || [];
                        self.failedFiles = data.failed_files || [];
                        self.ingestFiles = data.ingest_files || [];
                        self.config = data.config || {};
                        self.lastPoll = new Date();
                        self.pollError = false;
                        
                        // Update global status bar
                        window.dispatchEvent(new CustomEvent('system-status', { detail: data }));
                    })
                    .catch(function(err) {
                        self.pollError = true;
                        console.error('Status poll failed:', err);
                    });
            },

            // Watcher state helpers
            get watcherState() {
                return this.watcher.state || 'unknown';
            },
            get watcherLabel() {
                var s = this.watcherState;
                if (s === 'idle' || s === 'scanning') return 'Watching';
                if (s === 'processing') return 'Processing';
                if (s === 'error') return 'Error';
                if (s === 'stopped') return 'Stopped';
                if (s === 'not_started') return 'Not Started';
                return s;
            },
            get watcherColor() {
                var s = this.watcherState;
                if (s === 'idle' || s === 'scanning') return 'var(--success)';
                if (s === 'processing') return 'var(--accent)';
                if (s === 'error') return 'var(--error)';
                return 'var(--text-tertiary)';
            },
            get isProcessing() { return this.watcherState === 'processing'; },
            get timeSinceLastScan() {
                var t = this.watcher.last_scan_at;
                if (!t) return 'never';
                return window.timeAgo(t);
            },

            // Ingest file counts
            get newFileCount() {
                return this.ingestFiles.filter(function(f) { return f.status === 'new'; }).length;
            },
            get processingFileCount() {
                return this.ingestFiles.filter(function(f) { return f.status === 'processing'; }).length;
            },
            get completedFileCount() {
                return this.ingestFiles.filter(function(f) { return f.status === 'completed'; }).length;
            },
            get failedFileCount() {
                return this.ingestFiles.filter(function(f) { return f.status === 'failed'; }).length;
            },

            // Actions
            clearFailed: function() {
                var self = this;
                fetch('/v2/api/clear-failed', { method: 'POST' })
                    .then(function() { self.poll(); })
                    .catch(function(err) { console.error('Clear failed:', err); });
            },
            skipFile: function(hash) {
                var self = this;
                fetch('/v2/api/skip-file/' + hash, { method: 'POST' })
                    .then(function() { self.poll(); })
                    .catch(function(err) { console.error('Skip file failed:', err); });
            },
            retryFile: function(hash) {
                var self = this;
                fetch('/v2/api/retry-file/' + hash, { method: 'POST' })
                    .then(function() { self.poll(); })
                    .catch(function(err) { console.error('Retry file failed:', err); });
            },
            resetExhaustedKeys: function() {
                var self = this;
                fetch('/v2/api/reset-exhausted-keys', { method: 'POST' })
                    .then(function() { self.poll(); })
                    .catch(function(err) { console.error('Reset keys failed:', err); });
            },

            // Format helpers
            formatFileSize: function(bytes) {
                if (!bytes) return '0 B';
                if (bytes < 1024) return bytes + ' B';
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
            },
            truncateError: function(err, maxLen) {
                if (!err) return '';
                maxLen = maxLen || 120;
                // Extract the meaningful part from verbose Gemini errors
                var match = err.match(/(\d{3}\s+\w+)[.:]?\s/);
                if (match) {
                    var idx = err.indexOf(match[1]);
                    var short = err.substring(idx, idx + maxLen);
                    return short.length < err.length - idx ? short + '...' : short;
                }
                return err.length > maxLen ? err.substring(0, maxLen) + '...' : err;
            },
            
            // Delegate to global format helpers for use in templates
            formatDate: function(d) { return window.formatDate ? window.formatDate(d) : (d || ''); },
            formatDuration: function(s) { return window.formatDuration ? window.formatDuration(s) : (s || ''); },
            formatTimestamp: function(t) { return window.formatTimestamp ? window.formatTimestamp(t) : (t || ''); },
        };
    });

    /**
     * Note list component
     */
    Alpine.data('inboxView', function(initialNotes, initialTagFilter) {
        return {
            notes: initialNotes || [],
            selectedId: null,
            filter: 'all',
            searchQuery: '',
            tagFilter: initialTagFilter || '',
            loading: false,
            knownProjects: [],
            
            init: function() {
                // Load known projects
                var self = this;
                fetch('/v2/api/projects')
                    .then(function(res) { return res.json(); })
                    .then(function(data) {
                        self.knownProjects = (data.projects || []).map(function(p) { return p.name; });
                    })
                    .catch(function(err) { console.warn('Failed to load projects:', err); });
            },
            
            get filteredNotes() {
                var filtered = this.notes;
                var self = this;
                
                if (self.filter !== 'all') {
                    filtered = filtered.filter(function(n) { return n.status === self.filter; });
                }
                
                if (self.tagFilter) {
                    var tagLower = self.tagFilter.toLowerCase();
                    filtered = filtered.filter(function(n) {
                        var tags = n.tags || [];
                        return tags.some(function(t) { return (t || '').toLowerCase() === tagLower; });
                    });
                }
                
                if (self.searchQuery) {
                    var q = self.searchQuery.toLowerCase();
                    filtered = filtered.filter(function(n) {
                        return (n.title || '').toLowerCase().includes(q) ||
                               (n.preview || '').toLowerCase().includes(q);
                    });
                }
                
                return filtered;
            },
            
            clearTagFilter: function() {
                this.tagFilter = '';
                // Update URL to remove tag param
                var url = new URL(window.location);
                url.searchParams.delete('tag');
                window.history.replaceState({}, '', url);
            },
            
            select: function(note) {
                this.selectedId = note.id;
                // For registry notes, lazy-load content if not already loaded
                if (note.source === 'registry' && !note._loaded) {
                    var self = this;
                    fetch('/v2/api/registry/' + note.id + '/preview')
                        .then(function(res) { return res.json(); })
                        .then(function(data) {
                            note.content = data.content || '';
                            note.transcript = data.transcript || '';
                            note.audio_url = data.audio_url || null;
                            note._loaded = true;
                        })
                        .catch(function() {});
                }
            },
            
            refresh: function() {
                var self = this;
                self.loading = true;
                fetch('/v2/api/notes')
                    .then(function(res) { return res.json(); })
                    .then(function(data) { self.notes = data; })
                    .catch(function(err) { console.error('Failed to load notes:', err); })
                    .finally(function() { self.loading = false; });
            },
            
            // Inspector Actions
            openAudio: function() {
                var note = this.filteredNotes.find(function(n) { return n.id === this.selectedId; }.bind(this));
                if (note && note.audio_url) {
                    window.open(note.audio_url, '_blank');
                }
            },
            
            openNote: function() {
                var note = this.filteredNotes.find(function(n) { return n.id === this.selectedId; }.bind(this));
                if (note) {
                    window.location.href = note.link || ('/v2/note/' + note.id);
                }
            },
            
            copyTranscript: function() {
                var note = this.filteredNotes.find(function(n) { return n.id === this.selectedId; }.bind(this));
                if (note && note.transcript) {
                    navigator.clipboard.writeText(note.transcript)
                        .then(function() {
                            console.log('Transcript copied to clipboard');
                            // TODO: Show toast notification
                        })
                        .catch(function(err) {
                            console.error('Failed to copy transcript:', err);
                        });
                }
            },
            
            downloadTranscript: function() {
                var note = this.filteredNotes.find(function(n) { return n.id === this.selectedId; }.bind(this));
                if (note && note.source === 'registry' && note.transcript) {
                    window.open('/v2/api/registry/' + note.id + '/download/transcript', '_blank');
                }
            },
            
            copyBreakdown: function() {
                var note = this.filteredNotes.find(function(n) { return n.id === this.selectedId; }.bind(this));
                if (note && note.content) {
                    navigator.clipboard.writeText(note.content)
                        .then(function() {
                            console.log('Breakdown copied to clipboard');
                            // TODO: Show toast notification
                        })
                        .catch(function(err) {
                            console.error('Failed to copy breakdown:', err);
                        });
                }
            },
            
            downloadBreakdown: function() {
                var note = this.filteredNotes.find(function(n) { return n.id === this.selectedId; }.bind(this));
                if (note && note.source === 'registry' && note.content) {
                    window.open('/v2/api/registry/' + note.id + '/download/note', '_blank');
                }
            },
            
            // Project assignment
            assignProject: function(projectName) {
                var note = this.filteredNotes.find(function(n) { return n.id === this.selectedId; }.bind(this));
                if (!note || note.source !== 'registry') return;
                
                var self = this;
                var projects = projectName ? [projectName] : [];
                
                // Optimistic update
                note.projects = projects;
                
                fetch('/v2/api/registry/' + note.id + '/projects', {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ projects: projects })
                })
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    self.toast('Project updated');
                })
                .catch(function(err) {
                    self.toast('Failed to update project. Please try again.');
                    console.error('Project update error:', err);
                });
            },
            
            createAndAssignProject: function(projectName) {
                var note = this.filteredNotes.find(function(n) { return n.id === this.selectedId; }.bind(this));
                if (!note || note.source !== 'registry') return;
                
                projectName = (projectName || '').trim();
                if (!projectName) return;
                
                var self = this;
                
                // Add to known projects
                if (!this.knownProjects.includes(projectName)) {
                    this.knownProjects.push(projectName);
                }
                
                // Assign the project
                this.assignProject(projectName);
            },
            
            toast: function(msg) {
                // Simple toast notification - TODO: Implement proper toast UI
                // For now, just log to console as a placeholder
                console.log('Toast:', msg);
            },
            
            // Format helpers for templates
            formatDate: function(d) { return window.formatDate ? window.formatDate(d) : (d || ''); },
            formatDuration: function(s) { return window.formatDuration ? window.formatDuration(s) : (s || ''); },
            timeAgo: function(d) { return window.timeAgo ? window.timeAgo(d) : (d || ''); }
        };
    });

    /**
     * Task list component
     */
    Alpine.data('taskList', function(initialTasks) {
        return {
            tasks: initialTasks || [],
            filter: 'pending',
            loading: false,
            
            get filteredTasks() {
                var self = this;
                if (self.filter === 'completed') {
                    return self.tasks.filter(function(t) { return t.completed; });
                }
                if (self.filter === 'pending') {
                    return self.tasks.filter(function(t) { return !t.completed; });
                }
                return self.tasks;
            },
            
            get completedCount() {
                return this.tasks.filter(function(t) { return t.completed; }).length;
            },
            
            get pendingCount() {
                return this.tasks.filter(function(t) { return !t.completed; }).length;
            },
            
            // Stats object for template compatibility
            get stats() {
                return {
                    pending: this.pendingCount,
                    completed: this.completedCount,
                    total: this.tasks.length
                };
            },
            
            toggle: function(task) {
                var newState = !task.completed;
                task.completed = newState;
                
                fetch('/v2/api/tasks/' + task.id, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ completed: newState })
                }).catch(function(err) {
                    task.completed = !newState;
                    console.error('Failed to update task:', err);
                });
            },
            
            refresh: function() {
                var self = this;
                self.loading = true;
                fetch('/v2/api/tasks')
                    .then(function(res) { return res.json(); })
                    .then(function(data) { self.tasks = data; })
                    .catch(function(err) { console.error('Failed to load tasks:', err); })
                    .finally(function() { self.loading = false; });
            }
        };
    });

    /**
     * Audio player component
     */
    Alpine.data('audioPlayer', function(audioUrl) {
        return {
            url: audioUrl || '',
            playing: false,
            currentTime: 0,
            duration: 0,
            audio: null,
            
            init: function() {
                var self = this;
                if (self.url) {
                    self.audio = new Audio(self.url);
                    self.audio.addEventListener('loadedmetadata', function() {
                        self.duration = self.audio.duration;
                    });
                    self.audio.addEventListener('timeupdate', function() {
                        self.currentTime = self.audio.currentTime;
                    });
                    self.audio.addEventListener('ended', function() {
                        self.playing = false;
                        self.currentTime = 0;
                    });
                }
            },
            
            toggle: function() {
                if (!this.audio) return;
                
                if (this.playing) {
                    this.audio.pause();
                } else {
                    this.audio.play();
                }
                this.playing = !this.playing;
            },
            
            seek: function(event) {
                if (!this.audio || !this.duration) return;
                
                var rect = event.target.getBoundingClientRect();
                var percent = (event.clientX - rect.left) / rect.width;
                this.audio.currentTime = percent * this.duration;
            },
            
            get progress() {
                return this.duration ? (this.currentTime / this.duration) * 100 : 0;
            },
            
            formatTime: function(seconds) {
                if (!seconds || isNaN(seconds)) return '0:00';
                var mins = Math.floor(seconds / 60);
                var secs = Math.floor(seconds % 60);
                return mins + ':' + (secs < 10 ? '0' : '') + secs;
            },
            
            destroy: function() {
                if (this.audio) {
                    this.audio.pause();
                    this.audio = null;
                }
            }
        };
    });

    /**
     * File upload component
     */
    Alpine.data('fileUpload', function() {
        return {
            files: [],
            uploading: false,
            progress: 0,
            dragover: false,
            
            handleDrop: function(event) {
                this.dragover = false;
                this.addFiles(event.dataTransfer.files);
            },
            
            handleSelect: function(event) {
                this.addFiles(event.target.files);
            },
            
            addFiles: function(fileList) {
                var self = this;
                var audioFiles = Array.from(fileList).filter(function(f) {
                    return f.type.startsWith('audio/') || 
                           /\.(m4a|mp3|wav|ogg|flac)$/i.test(f.name);
                });
                
                if (audioFiles.length === 0) {
                    alert('Please select audio files');
                    return;
                }
                
                audioFiles.forEach(function(f) {
                    self.files.push({
                        file: f,
                        name: f.name,
                        size: f.size,
                        status: 'pending'
                    });
                });
            },
            
            removeFile: function(index) {
                this.files.splice(index, 1);
            },
            
            upload: function() {
                var self = this;
                if (self.files.length === 0 || self.uploading) return;
                
                self.uploading = true;
                self.progress = 0;
                
                var uploadNext = function(i) {
                    if (i >= self.files.length) {
                        self.uploading = false;
                        return;
                    }
                    
                    var item = self.files[i];
                    if (item.status === 'done') {
                        uploadNext(i + 1);
                        return;
                    }
                    
                    item.status = 'uploading';
                    
                    var formData = new FormData();
                    formData.append('file', item.file);
                    
                    fetch('/v2/api/upload', {
                        method: 'POST',
                        body: formData
                    })
                    .then(function(res) {
                        if (!res.ok) throw new Error('Upload failed');
                        item.status = 'done';
                    })
                    .catch(function() {
                        item.status = 'error';
                    })
                    .finally(function() {
                        self.progress = ((i + 1) / self.files.length) * 100;
                        uploadNext(i + 1);
                    });
                };
                
                uploadNext(0);
            },
            
            formatSize: function(bytes) {
                if (bytes < 1024) return bytes + ' B';
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
            }
        };
    });

    /**
     * Tag picker component
     */
    Alpine.data('tagPicker', function(initialTags) {
        return {
            tags: initialTags || [],
            input: '',
            
            addTag: function(tag) {
                var trimmed = (tag || this.input).trim();
                if (trimmed && this.tags.indexOf(trimmed) === -1) {
                    this.tags.push(trimmed);
                }
                this.input = '';
            },
            
            removeTag: function(tag) {
                var idx = this.tags.indexOf(tag);
                if (idx > -1) this.tags.splice(idx, 1);
            },
            
            handleKeydown: function(event) {
                if (event.key === 'Enter' && this.input) {
                    event.preventDefault();
                    this.addTag();
                }
                if (event.key === 'Backspace' && !this.input && this.tags.length > 0) {
                    this.tags.pop();
                }
            }
        };
    });

    // ========================================================================
    // KEY MANAGER — CRUD for API keys
    // ========================================================================
    Alpine.data('keyManager', function(initialKeys) {
        return {
            keys: initialKeys || [],
            newKey: '',
            newName: '',
            adding: false,
            addError: '',

            addKey: function() {
                if (!this.newKey) return;
                var self = this;
                self.adding = true;
                self.addError = '';
                fetch('/v2/api/keys/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: self.newKey, name: self.newName })
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.error) { self.addError = data.error; }
                    else { self.newKey = ''; self.newName = ''; self.refreshKeys(); }
                })
                .catch(function(e) { self.addError = 'Network error'; })
                .finally(function() { self.adding = false; });
            },

            toggleKey: function(id) {
                var self = this;
                fetch('/v2/api/keys/' + id + '/toggle', { method: 'POST' })
                    .then(function() { self.refreshKeys(); });
            },

            resetKey: function(id) {
                var self = this;
                fetch('/v2/api/keys/' + id + '/reset', { method: 'POST' })
                    .then(function() { self.refreshKeys(); });
            },

            deleteKey: function(id) {
                if (!confirm('Delete this API key?')) return;
                var self = this;
                fetch('/v2/api/keys/' + id, { method: 'DELETE' })
                    .then(function() { self.refreshKeys(); });
            },

            resetAllExhausted: function() {
                var self = this;
                var exhausted = self.keys.filter(function(k) { return k.is_exhausted; });
                var promises = exhausted.map(function(k) {
                    return fetch('/v2/api/keys/' + k.id + '/reset', { method: 'POST' });
                });
                Promise.all(promises).then(function() { self.refreshKeys(); });
            },

            refreshKeys: function() {
                var self = this;
                fetch('/v2/api/keys')
                    .then(function(r) { return r.json(); })
                    .then(function(data) { self.keys = data.keys || []; });
            },

            truncErr: function(s) {
                if (!s) return '';
                return s.length > 50 ? s.substring(0, 50) + '...' : s;
            }
        };
    });

    // ========================================================================
    // CALENDAR VIEW — Heatmap grid with expandable day details
    // ========================================================================
    Alpine.data('calendarView', function() {
        var now = new Date();
        return {
            year: now.getFullYear(),
            month: now.getMonth(),  // 0-indexed
            dailyCounts: {},
            dailyNotes: {},
            dailyRollups: {},
            weeklyRollups: [],
            selectedDay: null,
            selectedDayData: {},
            loading: false,
            maxCount: 1,

            get monthLabel() {
                var months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
                return months[this.month] + ' ' + this.year;
            },

            get calendarCells() {
                var cells = [];
                var firstDay = new Date(this.year, this.month, 1);
                var lastDay = new Date(this.year, this.month + 1, 0);
                var startDow = (firstDay.getDay() + 6) % 7; // Mon=0
                var today = new Date();
                var todayStr = today.getFullYear() + '-' + ('0' + (today.getMonth()+1)).slice(-2) + '-' + ('0' + today.getDate()).slice(-2);

                // Previous month padding
                for (var i = startDow - 1; i >= 0; i--) {
                    var d = new Date(this.year, this.month, -i);
                    var ds = this._ds(d);
                    cells.push({ key: ds, day: d.getDate(), date: ds, inMonth: false, isToday: ds === todayStr, count: (this.dailyCounts[ds] || {}).total || 0, failed: (this.dailyCounts[ds] || {}).failed || 0 });
                }
                // Current month
                for (var day = 1; day <= lastDay.getDate(); day++) {
                    var d2 = new Date(this.year, this.month, day);
                    var ds2 = this._ds(d2);
                    cells.push({ key: ds2, day: day, date: ds2, inMonth: true, isToday: ds2 === todayStr, count: (this.dailyCounts[ds2] || {}).total || 0, failed: (this.dailyCounts[ds2] || {}).failed || 0 });
                }
                // Next month padding to fill 6 rows
                var rem = 42 - cells.length;
                for (var j = 1; j <= rem; j++) {
                    var d3 = new Date(this.year, this.month + 1, j);
                    var ds3 = this._ds(d3);
                    cells.push({ key: ds3, day: d3.getDate(), date: ds3, inMonth: false, isToday: ds3 === todayStr, count: (this.dailyCounts[ds3] || {}).total || 0, failed: (this.dailyCounts[ds3] || {}).failed || 0 });
                }
                return cells;
            },

            init: function() { this.loadMonth(); },

            loadMonth: function() {
                var self = this;
                self.loading = true;
                fetch('/v2/api/calendar-data?year=' + self.year + '&month=' + (self.month + 1))
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        self.dailyCounts = data.daily_counts || {};
                        self.dailyNotes = data.daily_notes || {};
                        self.dailyRollups = data.daily_rollups || {};
                        self.weeklyRollups = data.weekly_rollups || [];
                        // compute max
                        var m = 1;
                        Object.values(self.dailyCounts).forEach(function(v) { if (v.total > m) m = v.total; });
                        self.maxCount = m;
                        self.loading = false;
                    })
                    .catch(function() { self.loading = false; });
            },

            prevMonth: function() {
                if (this.month === 0) { this.month = 11; this.year--; }
                else { this.month--; }
                this.selectedDay = null;
                this.loadMonth();
            },
            nextMonth: function() {
                if (this.month === 11) { this.month = 0; this.year++; }
                else { this.month++; }
                this.selectedDay = null;
                this.loadMonth();
            },
            goToday: function() {
                var now = new Date();
                this.year = now.getFullYear();
                this.month = now.getMonth();
                this.selectedDay = null;
                this.loadMonth();
            },

            selectDay: function(dateStr) {
                if (this.selectedDay === dateStr) { this.selectedDay = null; return; }
                this.selectedDay = dateStr;
                this.selectedDayData = {
                    notes: this.dailyNotes[dateStr] || [],
                    rollup: this.dailyRollups[dateStr] || null
                };
            },

            heatColor: function(count) {
                if (count <= 0) return 'transparent';
                var intensity = Math.min(count / Math.max(this.maxCount, 1), 1);
                var alpha = 0.15 + intensity * 0.6;
                return 'rgba(56, 189, 248, ' + alpha + ')';
            },

            _ds: function(d) {
                return d.getFullYear() + '-' + ('0' + (d.getMonth()+1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
            }
        };
    });

    // ========================================================================
    // PROJECT VIEW — Mode-grouped notes with expansion
    // ========================================================================
    Alpine.data('projectView', function(initialProjects) {
        return {
            projects: initialProjects || [],
            expanded: null,
            expandedNotes: [],
            expandedLoading: false,
            
            // Create project modal
            showCreateModal: false,
            newProjectName: '',
            creating: false,
            createError: '',

            get totalNotes() {
                return this.projects.reduce(function(sum, p) { return sum + (p.count || 0); }, 0);
            },
            
            get projectCount() {
                return this.projects.filter(function(p) { return p.kind === 'project'; }).length;
            },
            
            get modeCount() {
                return this.projects.filter(function(p) { return p.kind === 'mode'; }).length;
            },

            toggle: function(proj) {
                var key = proj.kind + ':' + proj.name;
                if (this.expanded === key) { this.expanded = null; return; }
                this.expanded = key;
                this.expandedLoading = true;
                this.expandedNotes = proj.notes || [];
                this.expandedLoading = false;
            },
            
            isExpanded: function(proj) {
                return this.expanded === (proj.kind + ':' + proj.name);
            },

            formatName: function(proj) {
                if (!proj.name) return 'Unknown';
                if (proj.kind === 'project') return proj.name;
                // Format mode names
                return proj.name.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
            },

            getIcon: function(proj) {
                if (proj.kind === 'project') return '📁';
                var icons = {
                    'personal_note': '📝', 'meeting': '🤝', 'idea': '💡',
                    'journal': '📖', 'todo': '✅', 'voice_memo': '🎙️',
                    'brainstorm': '🧠', 'reflection': '🪞'
                };
                return icons[proj.name] || '📄';
            },

            getColor: function(proj) {
                if (proj.kind === 'project') return 'rgba(99,102,241,0.2)';
                var colors = {
                    'personal_note': 'rgba(56,189,248,0.2)', 'meeting': 'rgba(168,85,247,0.2)',
                    'idea': 'rgba(250,204,21,0.2)', 'journal': 'rgba(52,211,153,0.2)',
                    'todo': 'rgba(251,146,60,0.2)', 'voice_memo': 'rgba(236,72,153,0.2)',
                    'brainstorm': 'rgba(129,140,248,0.2)', 'reflection': 'rgba(45,212,191,0.2)'
                };
                return colors[proj.name] || 'rgba(148,163,184,0.2)';
            },
            
            // Create a new project
            createProject: function() {
                var self = this;
                var name = self.newProjectName.trim();
                if (!name) return;
                
                self.creating = true;
                self.createError = '';
                
                fetch('/v2/api/projects', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name })
                })
                .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
                .then(function(result) {
                    if (result.ok) {
                        // Add to local list
                        self.projects.unshift({ name: name, kind: 'project', count: 0, notes: [] });
                        self.showCreateModal = false;
                        self.newProjectName = '';
                    } else {
                        self.createError = result.data.detail || 'Failed to create project';
                    }
                })
                .catch(function(e) {
                    self.createError = 'Network error';
                })
                .finally(function() {
                    self.creating = false;
                });
            },
            
            // Delete a project
            confirmDelete: function(proj) {
                var self = this;
                if (proj.count > 0) {
                    alert('Cannot delete project with notes assigned. Remove notes first.');
                    return;
                }
                if (!confirm('Delete project "' + proj.name + '"? This will remove the folder from Obsidian.')) return;
                
                fetch('/v2/api/projects/' + encodeURIComponent(proj.name), { method: 'DELETE' })
                .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
                .then(function(result) {
                    if (result.ok) {
                        self.projects = self.projects.filter(function(p) { return p.name !== proj.name; });
                    } else {
                        alert(result.data.detail || 'Failed to delete project');
                    }
                })
                .catch(function() { alert('Network error'); });
            },
            
            // Legacy compatibility
            formatMode: function(mode) {
                return this.formatName({name: mode, kind: 'mode'});
            },
            modeIcon: function(mode) {
                return this.getIcon({name: mode, kind: 'mode'});
            },
            modeColor: function(mode) {
                return this.getColor({name: mode, kind: 'mode'});
            }
        };
    });

    // ========================================================================
    // ARCHIVE VIEW — Paginated filtered list of all processed notes
    // ========================================================================
    // ── Registry Note Viewer ──
    Alpine.data('registryNote', (initial, knownProjects) => ({
        note: initial || {},
        knownProjects: knownProjects || [],
        processing: false,
        message: '',
        tab: 'note',  // 'note' | 'transcript'

        // Tag/project UI state
        showTagInput: false,
        showProjectInput: false,
        newTag: '',
        newProject: '',

        // Computed-like
        get wordCount() {
            return this.note.content ? this.note.content.split(/\s+/).filter(Boolean).length : 0;
        },
        get readTime() {
            return Math.max(1, Math.ceil(this.wordCount / 200));
        },
        get transcriptWordCount() {
            return this.note.transcript ? this.note.transcript.split(/\s+/).filter(Boolean).length : 0;
        },
        get renderedContent() {
            if (!this.note.content) return '';
            if (typeof marked !== 'undefined') {
                try {
                    // Strip YAML frontmatter (---...---)
                    let text = this.note.content;
                    if (text.startsWith('---')) {
                        const end = text.indexOf('---', 3);
                        if (end !== -1) text = text.substring(end + 3).trim();
                    }
                    return marked.parse(text);
                } catch (e) { console.warn('marked error:', e); }
            }
            return '<pre style="white-space:pre-wrap;">' + this._escHtml(this.note.content) + '</pre>';
        },

        // Helpers
        formatDate(d) {
            if (!d) return '—';
            try { return new Date(d).toLocaleString('en-GB', { day:'numeric', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' }); }
            catch { return d; }
        },
        formatDuration(s) {
            if (!s) return '';
            const m = Math.floor(s / 60), sec = Math.floor(s % 60);
            return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
        },
        shortenPath(p) {
            if (!p) return '—';
            const parts = p.replace(/\\/g, '/').split('/');
            return parts.length > 3 ? '…/' + parts.slice(-3).join('/') : p;
        },
        highlightTimestamps(text) {
            return this._escHtml(text).replace(
                /\[(\d{1,2}:\d{2}(?::\d{2})?)\]/g,
                '<span class="timestamp">[$1]</span>'
            );
        },
        _escHtml(s) {
            const d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        },

        // ── Copy / Download ──
        copyContent() {
            const text = this.tab === 'note' ? this.note.content : this.note.transcript;
            if (text) {
                navigator.clipboard.writeText(text);
                this.toast('Copied to clipboard');
            }
        },
        download(type) {
            window.open(`/v2/api/registry/${this.note.id}/download/${type}`, '_blank');
        },

        // ── Tags ──
        async addTag() {
            const tag = this.newTag.trim().replace(/^#/, '').replace(/[^a-zA-Z0-9_-]/g, '');
            if (!tag || this.note.tags.includes(tag)) { this.newTag = ''; return; }
            this.note.tags.push(tag);
            this.newTag = '';
            this.showTagInput = false;
            await this._saveTags();
        },
        async removeTag(i) {
            this.note.tags.splice(i, 1);
            await this._saveTags();
        },
        async _saveTags() {
            try {
                await fetch(`/v2/api/registry/${this.note.id}/tags`, {
                    method: 'PUT', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ tags: this.note.tags })
                });
                this.toast('Tags updated');
            } catch (e) { this.toast('Failed to save tags'); }
        },

        // ── Projects ──
        async addProject() {
            const proj = this.newProject.trim();
            if (!proj || this.note.projects.includes(proj)) { this.newProject = ''; return; }
            this.note.projects.push(proj);
            if (!this.knownProjects.includes(proj)) this.knownProjects.push(proj);
            this.newProject = '';
            this.showProjectInput = false;
            await this._saveProjects();
        },
        async removeProject(i) {
            this.note.projects.splice(i, 1);
            await this._saveProjects();
        },
        async _saveProjects() {
            try {
                await fetch(`/v2/api/registry/${this.note.id}/projects`, {
                    method: 'PUT', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ projects: this.note.projects })
                });
                this.toast('Projects updated');
            } catch (e) { this.toast('Failed to save projects'); }
        },

        // ── Reprocess / Delete ──
        async reprocess() {
            if (!confirm('Reprocess this note? The file will be picked up again by the watcher.')) return;
            this.processing = true;
            try {
                const r = await fetch('/v2/api/registry/' + this.note.id + '/reprocess', { method: 'POST' });
                if (r.ok) {
                    this.toast('Queued for reprocessing');
                    setTimeout(() => window.location.href = '/v2/inbox', 1500);
                } else {
                    this.toast('Error: ' + (await r.text()));
                }
            } catch (e) { this.toast('Network error'); }
            this.processing = false;
        },
        async deleteNote() {
            if (!confirm('Permanently delete this note from the registry?')) return;
            try {
                const r = await fetch('/v2/api/registry/' + this.note.id, { method: 'DELETE' });
                if (r.ok) {
                    this.toast('Deleted');
                    setTimeout(() => window.location.href = '/v2/inbox', 1000);
                } else {
                    this.toast('Error: ' + (await r.text()));
                }
            } catch (e) { this.toast('Network error'); }
        },

        toast(msg) {
            this.message = msg;
            setTimeout(() => this.message = '', 2500);
        }
    }));

    Alpine.data('archiveView', function() {
        return {
            items: [],
            total: 0,
            page: 1,
            perPage: 25,
            totalPages: 1,
            statusFilter: 'all',
            fromDate: '',
            toDate: '',
            loading: false,

            init: function() { this.loadPage(); },

            loadPage: function() {
                var self = this;
                self.loading = true;
                var url = '/v2/api/archive?page=' + self.page + '&per_page=' + self.perPage + '&status=' + self.statusFilter;
                if (self.fromDate) url += '&from_date=' + self.fromDate;
                if (self.toDate) url += '&to_date=' + self.toDate;
                fetch(url)
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        self.items = data.items || [];
                        self.total = data.total || 0;
                        self.totalPages = data.total_pages || 1;
                        self.loading = false;
                    })
                    .catch(function() { self.loading = false; });
            },

            applyFilters: function() {
                this.page = 1;
                this.loadPage();
            },

            clearFilters: function() {
                this.statusFilter = 'all';
                this.fromDate = '';
                this.toDate = '';
                this.page = 1;
                this.loadPage();
            },

            goPage: function(p) {
                this.page = p;
                this.loadPage();
            },

            reprocessItem: function(id) {
                var self = this;
                fetch('/v2/api/registry/' + id + '/reprocess', { method: 'POST' })
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (data.success) self.loadPage();
                        else alert(data.error || 'Reprocess failed');
                    })
                    .catch(function() { alert('Network error'); });
            },

            deleteItem: function(id) {
                if (!confirm('Delete this processed note from the registry?')) return;
                var self = this;
                fetch('/v2/api/registry/' + id, { method: 'DELETE' })
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        if (data.success) self.loadPage();
                        else alert(data.error || 'Delete failed');
                    })
                    .catch(function() { alert('Network error'); });
            }
        };
    });

    console.log('L1 V2 ready');
});

// Utility functions
window.formatDate = function(dateStr) {
    if (!dateStr) return '';
    // Handle UTC timestamps without Z suffix
    var normalized = dateStr;
    if (!dateStr.endsWith('Z') && !dateStr.includes('+') && !dateStr.includes('-', 10)) {
        normalized = dateStr + 'Z';
    }
    var date = new Date(normalized);
    var now = new Date();
    var diff = now - date;
    
    if (diff < 0) return 'Just now';  // Handle future dates
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
    if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
    if (diff < 604800000) return Math.floor(diff / 86400000) + 'd ago';
    
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

window.formatDuration = function(seconds) {
    if (!seconds) return '';
    var mins = Math.floor(seconds / 60);
    var secs = Math.floor(seconds % 60);
    return mins + ':' + (secs < 10 ? '0' : '') + secs;
};

window.timeAgo = function(isoStr) {
    if (!isoStr) return 'never';
    // Stored timestamps are UTC - add Z if missing to ensure proper parsing
    var normalized = isoStr;
    if (!isoStr.endsWith('Z') && !isoStr.includes('+') && !isoStr.includes('-', 10)) {
        normalized = isoStr + 'Z';
    }
    var date = new Date(normalized);
    var now = new Date();
    var diff = (now - date) / 1000;  // seconds
    if (diff < 0) return 'just now';  // Handle future dates (clock drift)
    if (diff < 5) return 'just now';
    if (diff < 60) return Math.floor(diff) + 's ago';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
};

window.formatTimestamp = function(isoStr) {
    if (!isoStr) return '';
    var d = new Date(isoStr);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
};
