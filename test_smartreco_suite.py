import sys
import json
import logging
from app import app, db
from models import User, Product, Event, Recommendation, DigestLog, Enrollment
from vector_store import vector_store
from agent.workflow import recommendation_engine
from agent.observability import get_all_traces, AGENT_TRACES
from scheduler import generate_proactive_digests_job

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("TestRunner")

def run_comprehensive_test_suite():
    print("\n=======================================================")
    print("STARTING SMARTRECO FULL IN-AND-OUT VERIFICATION SUITE")
    print("=======================================================\n")
    
    client = app.test_client()
    passed_tests = 0
    total_tests = 0

    def assert_test(name, condition):
        nonlocal passed_tests, total_tests
        total_tests += 1
        if condition:
            passed_tests += 1
            print(f"  [PASSED] Test {total_tests}: {name}")
        else:
            print(f"  [FAILED] Test {total_tests}: {name}")
            sys.exit(1)

    with app.app_context():
        # Re-seed database to pick up new course catalog items
        from seed_data import seed_database
        seed_database()

        # -------------------------------------------------------------
        # TEST 1: CATALOG INDEX PAGE & SEED DATA
        # -------------------------------------------------------------
        res = client.get('/')
        assert_test("Catalog Homepage returns HTTP 200 OK", res.status_code == 200)
        assert_test("Database contains seeded products", Product.query.count() >= 10)
        assert_test("ChromaDB Vector Store contains embeddings", vector_store.get_total_count() >= 10)

        # -------------------------------------------------------------
        # TEST 2: AUTHENTICATION & USER ROLES
        # -------------------------------------------------------------
        # Login as Admin
        res = client.post('/login', data={'email': 'admin@smartreco.com', 'password': 'admin'}, follow_redirects=True)
        assert_test("Admin user login successful", res.status_code == 200)
        
        # Register new test user
        test_email = "testsuite_user@smartreco.com"
        User.query.filter_by(email=test_email).delete()
        db.session.commit()

        res = client.post('/register', data={
            'name': 'Test Runner User',
            'email': test_email,
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        assert_test("New user registration redirected to OTP verification", res.status_code == 200)
        
        test_user = User.query.filter_by(email=test_email).first()
        assert_test("User persisted in SQLite database", test_user is not None)
        assert_test("Default user role is 'user' (Learner)", test_user.role == 'user')

        # Verify OTP for test_user
        res_otp = client.post('/verify_otp', data={'otp_code': test_user.otp_code}, follow_redirects=True)
        assert_test("6-Digit OTP Email Verification successful", res_otp.status_code == 200 and test_user.is_verified)

        # Login as test user
        client.post('/login', data={'email': test_email, 'password': 'password123'})

        # Test Profile GET
        res_prof = client.get('/profile')
        assert_test("User Profile page returns HTTP 200 OK", res_prof.status_code == 200)

        # Test Course Enrollment
        first_prod = Product.query.first()
        res_enr = client.post(f'/enroll/{first_prod.id}', follow_redirects=True)
        assert_test("Course Enrollment successful", res_enr.status_code == 200)
        assert_test("Enrollment saved in SQLite database", Enrollment.query.filter_by(user_id=test_user.id, product_id=first_prod.id).first() is not None)

        # Test AI Advisor Chatbot API
        res_chat = client.post('/api/chat', json={'message': 'Recommend Agentic AI courses'})
        assert_test("AI Learning Advisor Chatbot API returns HTTP 200 OK", res_chat.status_code == 200)
        assert_test("AI Advisor response contains RAG reply", 'reply' in res_chat.get_json())

        # Test Dedicated Full-Page AI Studio Assistant Route
        res_assist = client.get('/assistant')
        assert_test("Dedicated Full-Page AI Workstation returns HTTP 200 OK", res_assist.status_code == 200)

        # -------------------------------------------------------------
        # TEST 3: NON-BLOCKING BEHAVIORAL EVENT TRACKING API
        # -------------------------------------------------------------
        batch_payload = {
            'events': [
                {
                    'session_id': 'sess_suite_99',
                    'event_type': 'search',
                    'target_id': 'Agentic AI LangGraph',
                    'details': {'query': 'Agentic AI LangGraph RAG'},
                    'duration_ms': 0
                },
                {
                    'session_id': 'sess_suite_99',
                    'event_type': 'product_view',
                    'target_id': '1',
                    'details': {'product_title': 'Mastering Agentic AI & LangGraph Workflows', 'category': 'Generative AI & Agents'},
                    'duration_ms': 45000
                },
                {
                    'session_id': 'sess_suite_99',
                    'event_type': 'dwell_time',
                    'target_id': '2',
                    'details': {'product_title': 'Advanced Vector Search & RAG Architectures', 'category': 'Generative AI & Agents'},
                    'duration_ms': 30000
                }
            ]
        }
        res = client.post('/api/events/batch', json=batch_payload)
        assert_test("Event batch API returns HTTP 200", res.status_code == 200)
        data = res.get_json()
        assert_test("Event batch API saved all 3 events", data.get('saved_count') == 3)

        # Verify events recorded for test user
        user_events = Event.query.filter_by(user_id=test_user.id).all()
        assert_test("Behavioral events stored in SQLite Events table", len(user_events) >= 3)

        # -------------------------------------------------------------
        # TEST 4: DUAL-WRITE PRODUCT MANAGEMENT (CREATE, EDIT, DELETE)
        # -------------------------------------------------------------
        client.post('/login', data={'email': 'admin@smartreco.com', 'password': 'admin'})

        # Create New Product Dual-Write
        create_data = {
            'product_id': '',
            'title': 'Autonomous Multi-Agent Systems Masterclass',
            'category': 'Generative AI & Agents',
            'description': 'Master complex multi-agent graphs, reflection loops, and dynamic task delegation.',
            'price': '119.99',
            'rating': '4.9',
            'tags': 'Agents, Multi-Agent, Python, LangGraph'
        }
        res = client.post('/admin/product/save', data=create_data, follow_redirects=True)
        assert_test("Admin product creation returns HTTP 200", res.status_code == 200)
        
        new_prod = Product.query.filter_by(title='Autonomous Multi-Agent Systems Masterclass').first()
        assert_test("New product written to SQL DB", new_prod is not None)

        # Check Dual-Write in Vector DB via semantic search
        vector_matches = vector_store.semantic_search("Autonomous Multi-Agent Systems", top_k=3)
        found_in_vector = any(m['product_id'] == new_prod.id for m in vector_matches)
        assert_test("Dual-Write SUCCESS: New product indexed in ChromaDB Vector Store", found_in_vector)

        # Edit Existing Product Dual-Write
        edit_data = {
            'product_id': str(new_prod.id),
            'title': 'Autonomous Multi-Agent Systems Masterclass (Pro Edition)',
            'category': 'Generative AI & Agents',
            'description': 'Master complex multi-agent graphs, reflection loops, and dynamic task delegation with production tools.',
            'price': '149.99',
            'rating': '5.0',
            'tags': 'Agents, Multi-Agent, Python, LangGraph, Enterprise'
        }
        res = client.post('/admin/product/save', data=edit_data, follow_redirects=True)
        assert_test("Admin product edit returns HTTP 200", res.status_code == 200)

        updated_prod = db.session.get(Product, new_prod.id)
        assert_test("Product update persisted in SQL DB", updated_prod.title == 'Autonomous Multi-Agent Systems Masterclass (Pro Edition)' and updated_prod.price == 149.99)

        # -------------------------------------------------------------
        # TEST 5: AGENTIC RECOMMENDATION ENGINE & OBSERVABILITY TRACING
        # -------------------------------------------------------------
        client.post('/login', data={'email': test_email, 'password': 'password123'})
        
        res = client.post('/api/recommendations/refresh', json={'session_id': 'sess_suite_99'})
        assert_test("Recommendation refresh API returns HTTP 200", res.status_code == 200)
        
        reco_resp = res.get_json()
        assert_test("Recommendation response contains narrative", 'narrative' in reco_resp.get('recommendation', {}))
        assert_test("Recommendation response contains product IDs", len(reco_resp['recommendation'].get('recommended_product_ids', [])) > 0)

        # Check Agent Observability Traces
        traces = get_all_traces()
        assert_test("Observability module recorded agent execution trace", len(traces) > 0)
        latest_trace = traces[0]
        assert_test("Agent trace contains executed decision nodes", len(latest_trace.get('nodes_executed', [])) >= 4)

        # -------------------------------------------------------------
        # TEST 6: STRICT STUDENT-INTENT DRIVEN RECOMMENDATION TEST
        # -------------------------------------------------------------
        # Create a new user specifically searching for Cybersecurity / Hacking
        sec_email = "sec_student@smartreco.com"
        User.query.filter_by(email=sec_email).delete()
        db.session.commit()

        sec_user = User(email=sec_email, name="Cyber Learner", role="user")
        sec_user.set_password("pass123")
        db.session.add(sec_user)
        db.session.commit()

        sec_events = [
            {
                'session_id': 'sess_sec_01',
                'event_type': 'search',
                'target_id': 'Ethical Hacking Cybersecurity',
                'details': {'query': 'Ethical Hacking Penetration Testing Cybersecurity Bug Bounty'},
                'duration_ms': 0
            },
            {
                'session_id': 'sess_sec_01',
                'event_type': 'category_filter',
                'target_id': 'Cybersecurity',
                'details': {'category': 'Cybersecurity'},
                'duration_ms': 0
            }
        ]
        
        # Save events for sec_user
        for ev in sec_events:
            db.session.add(Event(
                user_id=sec_user.id,
                session_id=ev['session_id'],
                event_type=ev['event_type'],
                target_id=ev['target_id'],
                details_json=json.dumps(ev['details']),
                duration_ms=ev['duration_ms']
            ))
        db.session.commit()

        # Run recommendation engine for sec_user
        sec_event_dicts = [e.to_dict() for e in Event.query.filter_by(user_id=sec_user.id).all()]
        sec_result = recommendation_engine.run(sec_user.id, 'sess_sec_01', sec_event_dicts, trigger_reason="sec_intent_test")
        
        sec_rec_products = sec_result.get('recommended_products', [])
        assert_test("Security learner received recommended products", len(sec_rec_products) > 0)
        
        # Verify 100% of recommended courses belong to Cybersecurity domain
        all_cyber = all(p.get('category') == 'Cybersecurity' for p in sec_rec_products)
        assert_test("STRICT STUDENT INTENT: 100% of recommendations match Cybersecurity interest category", all_cyber)

        # -------------------------------------------------------------
        # TEST 7: SCHEDULED PROACTIVE DELIVERY (APSCHEDULER DIGESTS)
        # -------------------------------------------------------------
        client.post('/login', data={'email': 'admin@smartreco.com', 'password': 'admin'})
        
        res = client.post('/admin/digests/trigger_all', follow_redirects=True)
        assert_test("Proactive daily digest batch trigger returns HTTP 200", res.status_code == 200)
        
        digests = DigestLog.query.all()
        assert_test("Proactive email digests generated and saved to DB", len(digests) > 0)

        # -------------------------------------------------------------
        # TEST 8: ADMIN DELETE DUAL-WRITE & POWER COMMANDS
        # -------------------------------------------------------------
        res = client.post(f'/admin/product/delete/{new_prod.id}', follow_redirects=True)
        assert_test("Admin delete product returns HTTP 200", res.status_code == 200)
        
        deleted_sql = db.session.get(Product, new_prod.id)
        assert_test("Deleted product removed from SQL DB", deleted_sql is None)

        res = client.post('/admin/events/clear', follow_redirects=True)
        assert_test("Admin clear events command returns HTTP 200", res.status_code == 200)

        res = client.post('/admin/traces/clear', follow_redirects=True)
        assert_test("Admin clear traces command returns HTTP 200", res.status_code == 200)

    print("\n=======================================================")
    print(f"SMARTRECO SUITE RESULT: {passed_tests}/{total_tests} TESTS PASSED PERFECTLY!")
    print("=======================================================\n")

if __name__ == '__main__':
    run_comprehensive_test_suite()
