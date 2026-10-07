# app/services/data_manager.py
import os
import json
import uuid
import threading
from datetime import datetime, timedelta
from app.services.utils import normalize_text
from collections import OrderedDict

from .utils import normalize_text

class DataManager:
    def __init__(self, data_dir='data', socketio=None, chat_manager=None):
        self.data_dir = data_dir
        self.socketio = socketio
        self.chat_manager = chat_manager
        os.makedirs(self.data_dir, exist_ok=True)
        self.files = {
            'library': os.path.join(data_dir, 'library.json'),
            'answered': os.path.join(data_dir, 'answered_questions.json'),
            'unanswered': os.path.join(data_dir, 'unanswered_questions.json'),
            'notifications': os.path.join(data_dir, 'notifications.json'),
            'errors': os.path.join(data_dir, 'errors.json'),
            'pending': os.path.join(data_dir, 'pending_answers.json'),
            'reply_tokens': os.path.join(data_dir, 'reply_tokens.json'),
            'thread_info': os.path.join(data_dir, 'thread_info.json'),
            'archived_chats': os.path.join(data_dir, 'archived_chats.json'),
            'settings': os.path.join(data_dir, 'settings.json'),
            'survey_definition': os.path.join(data_dir, 'survey_definition.json'),
            'survey_results': os.path.join(data_dir, 'survey_results.json'),
            'prechat_submissions': os.path.join(data_dir, 'prechat_submissions.json'),
            'users': os.path.join(data_dir, 'users.json'),
            'flows': os.path.join(data_dir, 'flows.json')
        }
        self._lock = threading.Lock()
        self._load_all_data()

    def _load_all_data(self):
        with self._lock:
            self.library = self._load_json(self.files['library'], {})
            self._ensure_library_structure()
            self.answered_questions = self._load_json(self.files['answered'], [])
            self.unanswered_questions = self._load_json(self.files['unanswered'], [])
            self.notifications = self._load_json(self.files['notifications'], [])
            self.errors = self._load_json(self.files['errors'], [])
            self.pending_answers = self._load_json(self.files['pending'], {})
            self.reply_tokens = self._load_json(self.files['reply_tokens'], {})
            self.thread_info = self._load_json(self.files['thread_info'], {})
            self.archived_chats = self._load_json(self.files['archived_chats'], [])
            self.settings = self._load_json(self.files['settings'], {})
            self.survey_definition = self._load_json(self.files['survey_definition'], {})
            self.survey_results = self._load_json(self.files['survey_results'], [])
            self.prechat_submissions = self._load_json(self.files['prechat_submissions'], [])
            self.users = self._load_json(self.files['users'], [])
            self.flows = self._load_json(self.files['flows'], {})

    def _ensure_library_structure(self):
        """Ensures the library has the new '_responses' and 'intents' structure."""
        if '_responses' not in self.library or 'intents' not in self.library:
            self.library = {'_responses': {}, 'intents': {}}

    def _load_json(self, filepath, default):
        try:
            with open(filepath, 'rb') as f:
                raw_data = f.read()
            decoded_data = raw_data.decode('utf-8')
            return json.loads(decoded_data)
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
            return default

    def _save_json(self, data, filepath):
        json_string = json.dumps(data, indent=2, ensure_ascii=False)
        encoded_data = json_string.encode('utf-8')
        with open(filepath, 'wb') as f:
            f.write(encoded_data)

    def _emit_update(self, event_type, payload=None):
        """Emits a socket event if the socketio instance is available."""
        if self.socketio:
            self.socketio.emit('data_changed', {'type': event_type, 'payload': payload or {}})

    def get_settings(self):
        """Returns all settings."""
        with self._lock:
            return json.loads(json.dumps(self.settings))

    def save_settings(self, settings_data):
        """Saves the entire settings object."""
        with self._lock:
            self.settings = settings_data
            self._save_json(self.settings, self.files['settings'])
            self._emit_update('settings') # For future real-time updates

    def get_user(self, email):
        """Finds a user by email."""
        with self._lock:
            for user in self.users:
                if user.get('email') == email:
                    return user
        return None

    def add_user(self, email, hashed_password):
        """Adds a new user from the public signup form as a group admin."""
        with self._lock:
            # Check for duplicates
            if any(u.get('email') == email for u in self.users):
                return False, "E-posta adresi zaten mevcut."

            # New users from signup are always group admins
            new_user = {
                "id": str(uuid.uuid4()),
                "email": email,
                "password": hashed_password,
                "role": "group_admin",
                "group_id": email, # The group is identified by the admin's email
                "created_at": datetime.now().isoformat()
            }
            self.users.append(new_user)
            self._save_json(self.users, self.files['users'])
            return True, "Kullanıcı başarıyla oluşturuldu."

    def delete_user_from_group(self, user_id_to_delete, requesting_admin_user):
        """Deletes a user from a group, with safety checks."""
        with self._lock:
            user_to_delete = None
            for user in self.users:
                if user.get('id') == user_id_to_delete:
                    user_to_delete = user
                    break

            if not user_to_delete:
                return False, "Kullanıcı bulunamadı."

            # Security checks
            if user_to_delete.get('role') != 'user':
                return False, "Yalnızca 'user' rolündeki kullanıcılar silinebilir."

            if user_to_delete.get('group_id') != requesting_admin_user.get('group_id'):
                return False, "Bu kullanıcıyı silme yetkiniz yok."

            # Proceed with deletion
            self.users = [u for u in self.users if u.get('id') != user_id_to_delete]
            self._save_json(self.users, self.files['users'])
            return True, "Kullanıcı başarıyla silindi."

    def add_user_to_group(self, email, hashed_password, group_id, permissions, tags=None):
        """Adds a new user to a specific group with defined permissions and tags."""
        with self._lock:
            # Check for duplicates
            if any(u.get('email') == email for u in self.users):
                return False, "E-posta adresi zaten mevcut."

            new_user = {
                "id": str(uuid.uuid4()),
                "email": email,
                "password": hashed_password,
                "role": "user",
                "group_id": group_id,
                "permissions": permissions,
                "tags": tags if tags is not None else [],
                "created_at": datetime.now().isoformat()
            }
            self.users.append(new_user)
            self._save_json(self.users, self.files['users'])
            return True, "Kullanıcı başarıyla oluşturuldu."

    def update_user_tags(self, user_id_to_update, tags, requesting_admin_user):
        """Updates a user's tags within a group."""
        with self._lock:
            user_to_update = None
            user_index = -1
            for i, user in enumerate(self.users):
                if user.get('id') == user_id_to_update:
                    user_to_update = user
                    user_index = i
                    break

            if not user_to_update:
                return False, "Kullanıcı bulunamadı."

            # Security checks
            if user_to_update.get('role') != 'user':
                return False, "Yalnızca 'user' rolündeki kullanıcılar güncellenebilir."

            if user_to_update.get('group_id') != requesting_admin_user.get('group_id'):
                return False, "Bu kullanıcıyı güncelleme yetkiniz yok."

            # Proceed with update
            self.users[user_index]['tags'] = tags if tags is not None else []

            self._save_json(self.users, self.files['users'])
            # Return the updated user object
            return True, self.users[user_index]

    def get_survey_definition(self):
        """Returns the entire survey definition object."""
        with self._lock:
            # Return a copy to prevent mutation
            return json.loads(json.dumps(self.survey_definition))

    def save_survey_definition(self, definition_data):
        """Saves the entire survey definition object."""
        with self._lock:
            self.survey_definition = definition_data
            self._save_json(self.survey_definition, self.files['survey_definition'])
            # We might want a socket update here in the future

    def save_survey_result(self, result_data):
        """Appends a new survey result to the survey_results file."""
        with self._lock:
            # Add metadata to the result
            result_data['submission_id'] = str(uuid.uuid4())
            result_data['timestamp'] = datetime.now().isoformat()
            self.survey_results.insert(0, result_data) # Add to the beginning
            self._save_json(self.survey_results, self.files['survey_results'])
            # Maybe emit an update for a live dashboard in the future
            # self._emit_update('survey_results')
            return True

    def get_survey_results(self, search_term=None):
        """Returns all survey results, optionally filtered by a search term."""
        with self._lock:
            results = json.loads(json.dumps(self.survey_results))

        if search_term:
            term = search_term.lower()
            return [
                r for r in results
                if term in r.get('submission_id', '').lower() or \
                   term in r.get('chat_session_id', '').lower() or \
                   any(term in str(v).lower() for k, v in r.items() if k not in ['submission_id', 'timestamp', 'chat_session_id'])
            ]
        return results

    def save_prechat_submission(self, submission_data):
        """Appends a new pre-chat submission to the prechat_submissions file."""
        with self._lock:
            submission_data['submission_id'] = str(uuid.uuid4())
            submission_data['timestamp'] = datetime.now().isoformat()
            self.prechat_submissions.insert(0, submission_data)
            self._save_json(self.prechat_submissions, self.files['prechat_submissions'])
            self._emit_update('prechat_submissions')
            return True

    def get_prechat_submissions(self, search_term=None):
        """Returns all pre-chat submissions, optionally filtered by a search term."""
        with self._lock:
            submissions = json.loads(json.dumps(self.prechat_submissions))

        if search_term:
            term = search_term.lower()
            return [
                s for s in submissions
                if term in s.get('submission_id', '').lower() or \
                   term in s.get('user_id', '').lower() or \
                   any(term in str(v).lower() for k, v in s.items() if k not in ['submission_id', 'user_id', 'timestamp'])
            ]
        return submissions

    def remove_prechat_submissions(self, submission_ids_to_delete):
        """Removes pre-chat submissions by their submission_id."""
        with self._lock:
            original_count = len(self.prechat_submissions)
            self.prechat_submissions = [
                s for s in self.prechat_submissions
                if s.get('submission_id') not in submission_ids_to_delete
            ]
            deleted_count = original_count - len(self.prechat_submissions)
            if deleted_count > 0:
                self._save_json(self.prechat_submissions, self.files['prechat_submissions'])
                self._emit_update('prechat_submissions')
            return deleted_count

    def remove_survey_results(self, submission_ids_to_delete):
        """Removes survey results by their submission_id."""
        with self._lock:
            original_count = len(self.survey_results)
            self.survey_results = [
                r for r in self.survey_results
                if r.get('submission_id') not in submission_ids_to_delete
            ]
            deleted_count = original_count - len(self.survey_results)
            if deleted_count > 0:
                self._save_json(self.survey_results, self.files['survey_results'])
                self._emit_update('survey_results')
            return deleted_count

    def get_library(self, search_term=None):
        """Returns a resolved library, combining intents and their response data."""
        with self._lock:
            # Deep copy to prevent modification of the original data
            responses = json.loads(json.dumps(self.library.get('_responses', {})))
            intents = json.loads(json.dumps(self.library.get('intents', {})))

        resolved_library = {}
        for intent_key, intent_info in intents.items():
            response_id = intent_info.get('response_id')
            if response_id and response_id in responses:
                resolved_library[intent_key] = responses[response_id]

        if search_term:
            term = search_term.lower()
            return {
                k: v for k, v in resolved_library.items()
                if term in k.lower() or any(term in resp.lower() for resp in v.get('responses', []))
            }
        return resolved_library

    def get_intent_data(self, intent_key):
        """Gets the full response block for a given intent key."""
        with self._lock:
            intent_info = self.library.get('intents', {}).get(intent_key)
            if not intent_info:
                return None
            response_id = intent_info.get('response_id')
            return self.library.get('_responses', {}).get(response_id)

    def get_intents(self):
        """Returns just the intents part of the library, for the NLU service."""
        with self._lock:
            return self.library.get('intents', {})

    def get_intent_keys_for_response_id(self, response_id):
        """Returns a list of intent keys that map to a specific response_id."""
        with self._lock:
            intents = self.library.get('intents', {})
            return [key for key, info in intents.items() if info.get('response_id') == response_id]

    def get_flow(self, flow_id):
        """Returns the definition for a specific flow."""
        with self._lock:
            return self.flows.get(flow_id)

    def get_all_flows(self):
        """Returns all flow definitions."""
        with self._lock:
            return self.flows

    def save_flow(self, flow_id, flow_data):
        """Creates or updates a flow definition."""
        with self._lock:
            self.flows[flow_id] = flow_data
            self._save_json(self.flows, self.files['flows'])
            self._emit_update('flows') # For potential real-time updates
        return True

    def delete_flow(self, flow_id):
        """Deletes a flow definition."""
        with self._lock:
            if flow_id in self.flows:
                del self.flows[flow_id]
                self._save_json(self.flows, self.files['flows'])
                self._emit_update('flows')
                return True
            return False

    def delete_response_group(self, response_id):
        """Deletes an entire response group by its response_id."""
        with self._lock:
            # Find all intent keys associated with this response ID
            keys_to_delete = [
                key for key, info in self.library['intents'].items()
                if info.get('response_id') == response_id
            ]

            if not keys_to_delete:
                # If there are no intents, it might be an orphaned response.
                # Just try to delete the response itself.
                if self.library['_responses'].pop(response_id, None):
                    self._save_json(self.library, self.files['library'])
                    self._emit_update('library')
                    return 1 # Indicate one group was deleted
                return 0

            # Use the existing remove_from_library to delete the intents
            # and trigger the garbage collection for the response.
            return self.remove_from_library(keys_to_delete)

    def remove_from_library(self, keys_to_delete):
        """Removes intents and garbage collects orphaned responses."""
        with self._lock:
            deleted_count = 0
            for key in keys_to_delete:
                if self.library['intents'].pop(key, None):
                    deleted_count += 1

            if deleted_count > 0:
                self._garbage_collect_responses()
                self._save_json(self.library, self.files['library'])
                self._emit_update('library')
                self._emit_update('dashboard')
            return deleted_count

    def _garbage_collect_responses(self):
        """Removes responses that are no longer referenced by any intent."""
        used_response_ids = {info['response_id'] for info in self.library['intents'].values()}
        self.library['_responses'] = {
            resp_id: resp_data for resp_id, resp_data in self.library['_responses'].items()
            if resp_id in used_response_ids
        }

    def _get_canonical_representation(self, block):
        """Creates a consistent string representation of a response block."""
        if 'bubbles' in block and block['bubbles']:
            block['bubbles'] = sorted(block['bubbles'], key=lambda x: x.get('text', ''))
        sorted_block = OrderedDict(sorted(block.items()))
        return json.dumps(sorted_block)

    def _find_or_create_response_id(self, response_block):
        """Finds an existing response_id for a block, or creates a new one."""
        canonical_rep = self._get_canonical_representation(response_block.copy())

        for resp_id, resp_data in self.library['_responses'].items():
            if self._get_canonical_representation(resp_data.copy()) == canonical_rep:
                return resp_id

        # Not found, create a new one
        new_id_num = len(self.library['_responses'])
        while f"RESP_{new_id_num:04d}" in self.library['_responses']:
            new_id_num += 1

        new_id = f"RESP_{new_id_num:04d}"
        self.library['_responses'][new_id] = response_block
        return new_id

    def create_response_group(self, response_data, intents_list):
        """
        Creates a completely new response group.
        """
        with self._lock:
            # First, create a new response_id for the response data.
            # _find_or_create_response_id is perfect for this, as it also handles
            # finding duplicates to prevent identical response blocks.
            response_id = self._find_or_create_response_id(response_data)

            # Now, associate all the new intents with this new response_id.
            for intent in intents_list:
                # This will create new intents or overwrite existing ones, which is desired.
                self.library['intents'][intent] = {'response_id': response_id}

            self._save_json(self.library, self.files['library'])
            self._emit_update('library')
            # Return the ID of the created group so the frontend can reference it.
            return response_id

    def update_response_group(self, response_id, new_response_data, new_intents_list):
        """
        Updates a response group, including its response data and the list of
        intents that point to it.
        """
        with self._lock:
            if response_id not in self.library['_responses']:
                return False

            # 1. Update the response block itself
            if 'bubbles' in new_response_data and not new_response_data['bubbles']:
                del new_response_data['bubbles']
            self.library['_responses'][response_id] = new_response_data

            # 2. Reconcile the intents
            # Find all intents currently pointing to this response_id
            old_intents = {
                intent for intent, data in self.library['intents'].items()
                if data.get('response_id') == response_id
            }
            new_intents_set = set(new_intents_list)

            # Intents to remove (were in old, not in new)
            intents_to_delete = old_intents - new_intents_set
            for intent in intents_to_delete:
                self.library['intents'].pop(intent, None)

            # Intents to add or update
            for intent in new_intents_set:
                self.library['intents'][intent] = {'response_id': response_id}

            self._save_json(self.library, self.files['library'])
            self._emit_update('library')
            return True

    def get_library_grouped_by_response(self, search_term=None):
        """Returns the library grouped by responses, for admin UI display."""
        with self._lock:
            responses = json.loads(json.dumps(self.library.get('_responses', {})))
            intents = json.loads(json.dumps(self.library.get('intents', {})))

        grouped = {}
        for resp_id, resp_data in responses.items():
            grouped[resp_id] = resp_data
            grouped[resp_id]['intents'] = []

        for intent_key, intent_data in intents.items():
            resp_id = intent_data.get('response_id')
            if resp_id in grouped:
                grouped[resp_id]['intents'].append(intent_key)

        if search_term:
            term = search_term.lower()
            return {
                k: v for k, v in grouped.items()
                if any(term in intent.lower() for intent in v['intents']) or \
                   any(term in resp.lower() for resp in v.get('responses', []))
            }
        return grouped

    def train_from_answered(self, ids_to_train):
        with self._lock:
            trained_count = 0
            items_to_keep = []

            for item in self.answered_questions:
                if item.get('id') in ids_to_train:
                    normalized_question = normalize_text(item['question'])

                    response_block = {
                        "responses": [item['answer']],
                        "original_question": item['question']
                    }

                    response_id = self._find_or_create_response_id(response_block)

                    self.library['intents'][normalized_question] = {'response_id': response_id}
                    trained_count += 1
                else:
                    items_to_keep.append(item)

            if trained_count > 0:
                self.answered_questions = items_to_keep
                self._save_json(self.answered_questions, self.files['answered'])
                self._save_json(self.library, self.files['library'])
                self._emit_update('answered')
                self._emit_update('library')
                self._emit_update('dashboard')
            return trained_count

    def train_group_from_answered(self, ids_to_train, shared_response_block):
        """Trains a group of answered questions to a single shared response."""
        with self._lock:
            # Ensure the response block is clean
            if 'bubbles' in shared_response_block and not shared_response_block['bubbles']:
                del shared_response_block['bubbles']

            response_id = self._find_or_create_response_id(shared_response_block)

            trained_count = 0
            items_to_keep = []

            for item in self.answered_questions:
                if item.get('id') in ids_to_train:
                    normalized_question = normalize_text(item['question'])
                    self.library['intents'][normalized_question] = {'response_id': response_id}
                    trained_count += 1
                else:
                    items_to_keep.append(item)

            if trained_count > 0:
                self.answered_questions = items_to_keep
                self._save_json(self.answered_questions, self.files['answered'])
                self._save_json(self.library, self.files['library'])
                self._emit_update('answered')
                self._emit_update('library')
                self._emit_update('dashboard')

            return trained_count

    def regroup_intents(self, intent_keys, new_response_block):
        """Re-assigns a list of intents to a new or existing shared response block."""
        with self._lock:
            if not intent_keys:
                return 0

            # Find or create a response ID for the new shared block
            response_id = self._find_or_create_response_id(new_response_block)

            # Re-assign all specified intents to the new response_id
            for intent_key in intent_keys:
                self.library['intents'][intent_key] = {'response_id': response_id}

            # Clean up any responses that might have been orphaned
            self._garbage_collect_responses()
            self._save_json(self.library, self.files['library'])
            self._emit_update('library')

            return len(intent_keys)

    # --- Unchanged methods below ---
    def get_answered_questions(self, search_term=None):
        with self._lock:
            items = self.answered_questions.copy()
        if search_term:
            term = search_term.lower()
            return [
                item for item in items
                if term in item.get('question', '').lower() or term in item.get('answer', '').lower()
            ]
        return items

    def get_unanswered_questions(self, search_term=None):
        with self._lock:
            items = list(self.unanswered_questions)
        if search_term:
            term = search_term.lower()
            return [q for q in items if term in q.lower()]
        return items

    def get_notifications(self, search_term=None):
        with self._lock:
            items = self.notifications.copy()
        if search_term:
            term = search_term.lower()
            return [
                item for item in items
                if term in item.get('message', '').lower()
            ]
        return items
    def get_errors(self):
        with self._lock: return self.errors.copy()

    def add_unanswered_question(self, question):
        # Sorular her zaman orijinal haliyle saklanır. Normalizasyon sadece anahtar olarak kullanılır.
        with self._lock:
            # Listede olup olmadığını kontrol ederken normalize edilmiş hallerini karşılaştır.
            normalized_question = normalize_text(question)
            is_present = any(normalize_text(q) == normalized_question for q in self.unanswered_questions)

            if not is_present:
                self.unanswered_questions.insert(0, question)
                self._save_json(self.unanswered_questions, self.files['unanswered'])
                self._emit_update('unanswered')
                self._emit_update('dashboard')
                return True
        return False

    def save_new_answer(self, question, answer):
        with self._lock:
            # Orijinal soru metnini kullanarak yeni cevaplanmış soruyu ekle
            new_entry = {"id": str(uuid.uuid4()), "question": question, "answer": answer}

            # Mevcut cevaplanmış sorular listesinden aynı soruyu (normalize edilmiş) kaldır
            normalized_question = normalize_text(question)
            self.answered_questions = [
                item for item in self.answered_questions
                if normalize_text(item.get('question', '')) != normalized_question
            ]
            self.answered_questions.insert(0, new_entry)
            self._save_json(self.answered_questions, self.files['answered'])
            self._emit_update('answered')

            # Cevaplanmamışlar listesinden aynı soruyu (normalize edilmiş) kaldır
            unanswered_before_count = len(self.unanswered_questions)
            self.unanswered_questions = [
                q for q in self.unanswered_questions
                if normalize_text(q) != normalized_question
            ]
            if len(self.unanswered_questions) < unanswered_before_count:
                self._save_json(self.unanswered_questions, self.files['unanswered'])
                self._emit_update('unanswered')

            self._emit_update('dashboard')
            return True

    def create_reply_token(self, question):
        # Token oluştururken de orijinal soruyu sakla
        with self._lock:
            token = str(uuid.uuid4())
            self.reply_tokens[token] = question
            self._save_json(self.reply_tokens, self.files['reply_tokens'])
            return token

    def get_question_from_reply_token(self, token):
        with self._lock:
            question = self.reply_tokens.pop(token, None)
            if question:
                self._save_json(self.reply_tokens, self.files['reply_tokens'])
            return question

    def get_token_for_question(self, question_text):
        """Finds a reply token for a given question text without consuming it."""
        with self._lock:
            normalized_question_text = normalize_text(question_text)
            # Find the token by matching the normalized question value
            for token, question in self.reply_tokens.items():
                if normalize_text(question) == normalized_question_text:
                    return token
        return None

    def save_thread_info(self, reply_token, message_id, display_id):
        """Saves threading information (Message-ID and display_id) against a reply token."""
        with self._lock:
            self.thread_info[reply_token] = {
                "message_id": message_id,
                "display_id": display_id
            }
            self._save_json(self.thread_info, self.files['thread_info'])

    def get_thread_info(self, reply_token):
        """Retrieves threading information for a given reply token."""
        with self._lock:
            return self.thread_info.get(reply_token)

    def consume_thread_info(self, reply_token):
        """Removes threading information from the system after it has been used."""
        with self._lock:
            if reply_token in self.thread_info:
                self.thread_info.pop(reply_token)
                self._save_json(self.thread_info, self.files['thread_info'])

    def add_pending_question(self, question, reply_token=None, sid=None):
        with self._lock:
            request_id = str(uuid.uuid4())
            self.pending_answers[request_id] = {
                "question": question,
                "answer": None,
                "timestamp": datetime.now().isoformat(),
                "reply_token": reply_token,
                "sid": sid  # Store the socket session ID
            }
            self._save_json(self.pending_answers, self.files['pending'])
            return request_id

    def add_answer_to_pending(self, answer, reply_token=None, question=None):
        with self._lock:
            if not reply_token and not question:
                return

            target_sid = None
            normalized_question = normalize_text(question) if question else None

            # Cevabı, soru metni veya reply_token ile eşleştir.
            for request_id, data in self.pending_answers.items():
                if data.get('answer') is not None:
                    continue

                # Öncelikli olarak benzersiz olan jetonla eşleştir.
                token_match = reply_token and data.get('reply_token') == reply_token
                # Jeton yoksa, normalize edilmiş soru metniyle eşleştir.
                question_match = not token_match and normalized_question and normalize_text(data.get('question', '')) == normalized_question

                if token_match or question_match:
                    self.pending_answers[request_id]['answer'] = answer
                    target_sid = data.get('sid')
                    # Jetonlar benzersiz olduğu için ilk eşleşmede döngüden çıkılabilir.
                    if token_match:
                        break

            if target_sid and self.socketio:
                # First, log the message to the user's chat history
                if self.chat_manager:
                    self.chat_manager.add_message(target_sid, 'bot', answer)

                # Then, send the message to the user
                self.socketio.emit('new_message', {
                    'sender': 'bot', # Cevap bot/sistem tarafından verilmiş gibi gösterilir
                    'response': answer,
                    'bubbles': []
                }, room=target_sid)
                self._save_json(self.pending_answers, self.files['pending'])


    def check_pending_answer(self, request_id):
        with self._lock:
            pending_request = self.pending_answers.get(request_id)
            if pending_request and pending_request.get('answer'):
                answer = pending_request['answer']
                del self.pending_answers[request_id]
                self._save_json(self.pending_answers, self.files['pending'])
                return answer
            
            an_hour_ago = datetime.now() - timedelta(hours=1)
            cleaned_pending = {
                req_id: data for req_id, data in self.pending_answers.items()
                if datetime.fromisoformat(data['timestamp']) > an_hour_ago
            }
            if len(cleaned_pending) < len(self.pending_answers):
                self.pending_answers = cleaned_pending
                self._save_json(self.pending_answers, self.files['pending'])

            return None
            
    def remove_answered_questions(self, ids_to_delete):
        with self._lock:
            original_count = len(self.answered_questions)
            self.answered_questions = [item for item in self.answered_questions if item.get('id') not in ids_to_delete]
            if len(self.answered_questions) < original_count:
                self._save_json(self.answered_questions, self.files['answered'])
                self._emit_update('answered')
                self._emit_update('dashboard')
            return original_count - len(self.answered_questions)

    def remove_unanswered_questions(self, questions_to_delete):
        with self._lock:
            # Silinecek soruların normalize edilmiş hallerini bir set'e koy (hızlı arama için)
            normalized_to_delete = {normalize_text(q) for q in questions_to_delete}

            original_count = len(self.unanswered_questions)
            self.unanswered_questions = [
                q for q in self.unanswered_questions
                if normalize_text(q) not in normalized_to_delete
            ]

            if len(self.unanswered_questions) < original_count:
                self._save_json(self.unanswered_questions, self.files['unanswered'])
                self._emit_update('unanswered')
                self._emit_update('dashboard')
            return original_count - len(self.unanswered_questions)

    def clear_unanswered_questions(self):
        """Tüm cevaplanmamış soruları temizler."""
        with self._lock:
            if not self.unanswered_questions:
                return 0  # Silinecek bir şey yok

            original_count = len(self.unanswered_questions)
            self.unanswered_questions = []
            self._save_json(self.unanswered_questions, self.files['unanswered'])
            self._emit_update('unanswered')
            self._emit_update('dashboard')
            return original_count

    def add_notification(self, message, notification_type='info', sid=None, question_text=None, user_name=None, chat_display_id=None):
        """Adds a new notification."""
        with self._lock:
            new_notification = {
                "id": str(uuid.uuid4()),
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "type": notification_type,
                "sid": sid,
                "user_name": user_name,
                "chat_display_id": chat_display_id
            }
            if notification_type == 'human_request':
                new_notification['status'] = 'active'
            if question_text:
                new_notification['question'] = question_text

            self.notifications.insert(0, new_notification)
            # Keep the list size manageable
            self.notifications = self.notifications[:100]
            self._save_json(self.notifications, self.files['notifications'])
            self._emit_update('notifications')

    def remove_notifications(self, ids_to_delete):
        with self._lock:
            original_count = len(self.notifications)
            self.notifications = [n for n in self.notifications if n.get('id') not in ids_to_delete]
            if len(self.notifications) < original_count:
                self._save_json(self.notifications, self.files['notifications'])
                self._emit_update('notifications')
            return original_count - len(self.notifications)

    def remove_notifications_by_sid(self, sid):
        """Removes all 'human_request' notifications for a given session ID."""
        with self._lock:
            original_count = len(self.notifications)
            # Keep notifications that DO NOT match the criteria for removal
            self.notifications = [
                n for n in self.notifications
                if not (n.get('sid') == sid and n.get('type') == 'human_request')
            ]
            if len(self.notifications) < original_count:
                self._save_json(self.notifications, self.files['notifications'])
                # Emit an update so the frontend can refresh badges/lists
                self._emit_update('notifications')
            return original_count - len(self.notifications)

    def update_human_request_notification_status(self, sid, status):
        """Finds a 'human_request' notification by SID and updates its status."""
        with self._lock:
            notification_found = False
            for notification in self.notifications:
                if notification.get('sid') == sid and notification.get('type') == 'human_request':
                    notification['status'] = status
                    notification_found = True
                    break

            if notification_found:
                self._save_json(self.notifications, self.files['notifications'])
                self._emit_update('notifications')

            return notification_found

    def archive_chat(self, session_data):
        """Appends a completed chat session to the archive."""
        with self._lock:
            # chronological order
            self.archived_chats.insert(0, session_data)
            self._save_json(self.archived_chats, self.files['archived_chats'])
            self._emit_update('archives') # For future real-time updates

    def get_archived_chats(self, search_term=None):
        """Returns all archived chats, optionally filtered by a search term."""
        with self._lock:
            # Make a copy to prevent modification of the original data
            chats = json.loads(json.dumps(self.archived_chats))

        if search_term:
            term = search_term.lower()
            return [
                chat for chat in chats
                if term in chat.get('chat_display_id', '').lower() or \
                   term in chat.get('user_id', '').lower() or \
                   any(term in message.get('text', '').lower() for message in chat.get('history', []))
            ]
        return chats

    def remove_archived_chats(self, chat_ids_to_delete):
        """Removes archived chats by their chat_display_id."""
        with self._lock:
            original_count = len(self.archived_chats)
            self.archived_chats = [
                chat for chat in self.archived_chats
                if chat.get('chat_display_id') not in chat_ids_to_delete
            ]
            deleted_count = original_count - len(self.archived_chats)
            if deleted_count > 0:
                self._save_json(self.archived_chats, self.files['archived_chats'])
                self._emit_update('archives')
            return deleted_count

    def archive_telegram_chat(self, conversation_history, chat_type):
        """
        Archives a Telegram chat, appends it to the main archive file,
        and emits a socket event.
        """
        if not conversation_history:
            return False

        with self._lock:
            first_message = conversation_history[0]
            user = first_message.get('from', {})

            history_formatted = []
            for msg in conversation_history:
                sender_info = msg.get('from', {})
                sender_name = f"{sender_info.get('first_name', '')} {sender_info.get('last_name', '')}".strip()
                history_formatted.append({
                    'sender': sender_name or 'Bilinmiyor',
                    'text': msg.get('text', ''),
                    'timestamp': datetime.fromtimestamp(msg.get('date')).isoformat()
                })

            archive_entry = {
                'chat_display_id': f"TELEGRAM-{first_message.get('chat', {}).get('id')}-{first_message.get('message_id')}",
                'user_id': user.get('id'),
                'user_name': f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
                'start_time': datetime.fromtimestamp(first_message.get('date')).isoformat(),
                'history': history_formatted,
                'is_telegram_chat': True,
                'chat_type': chat_type
            }

            self.archived_chats.insert(0, archive_entry)
            self._save_json(self.archived_chats, self.files['archived_chats'])

            # Emit the update for the frontend. The page name is 'archives'.
            self._emit_update('archives')

            return True
