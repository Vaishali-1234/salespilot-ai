"""Page 5: Appointment Management."""

from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

from frontend.api_client import api_client
from frontend.styles import render_hero


def render_appointments_page() -> None:
    render_hero(
        "Appointment Management",
        "Check consultation availability, confirm bookings, prevent double-booking, and manage scheduled demos.",
    )

    c_avail, c_book = st.columns([1.0, 1.3], gap="large")
    with c_avail:
        st.markdown("### Check Slot Availability")
        default_date = (datetime.now() + timedelta(days=1)).date()
        picked_date = st.date_input("Select Consultation Date", value=default_date)
        date_str = picked_date.strftime("%Y-%m-%d")
        avail = api_client.check_availability(date_str)
        st.write("**Available Slots:**")
        if avail["available_slots"]:
            st.success(", ".join(avail["available_slots"]))
        else:
            st.warning("All slots on this date are booked.")
        if avail["booked_slots"]:
            st.write("**Already Booked:**", ", ".join(avail["booked_slots"]))

    with c_book:
        st.markdown("### Book Consultation (With Confirmation Guard)")
        leads = api_client.list_leads().get("leads", [])
        if not leads:
            st.info("Create or qualify a lead in Live AI Sales Agent first before booking an appointment.")
        else:
            lead_map = {f"#{l['id']} — {l['name'] or 'Unnamed'} ({l['email'] or 'no-email'})": l for l in leads}
            chosen_key = st.selectbox("Select CRM Lead", list(lead_map.keys()))
            chosen_lead = lead_map[chosen_key]

            with st.form("book_appt_form"):
                cname = st.text_input("Customer Name", value=chosen_lead.get("name") or "")
                cemail = st.text_input("Customer Email", value=chosen_lead.get("email") or "")
                slot_choice = st.selectbox("Time Slot", avail["available_slots"] or ["No slots available"])
                topic = st.text_input("Meeting Topic", value="TechNova Solutions Technical Discovery Demo")
                confirmed = st.checkbox("Customer has explicitly confirmed this date, time, and contact info")
                submit_btn = st.form_submit_button("Confirm & Book Appointment", type="primary")
                if submit_btn:
                    if not avail["available_slots"]:
                        st.error("No available slots for this date.")
                    elif not confirmed:
                        st.error("Customer confirmation checkbox is required before creating an appointment.")
                    else:
                        try:
                            api_client.book_appointment(
                                {
                                    "lead_id": chosen_lead["id"],
                                    "customer_name": cname,
                                    "customer_email": cemail,
                                    "appointment_date": date_str,
                                    "appointment_time": slot_choice,
                                    "topic": topic,
                                    "confirmed_by_customer": True,
                                }
                            )
                            st.success(f"Appointment booked for {cname} on {date_str} at {slot_choice}!")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Booking rejected: {exc}")

    st.markdown("### Scheduled & Cancelled Appointments")
    status_filter = st.selectbox("Filter by Status", ["All", "Confirmed", "Cancelled"])
    appts = api_client.list_appointments(status=status_filter).get("appointments", [])
    if appts:
        st.dataframe(pd.DataFrame(appts), use_container_width=True, hide_index=True)
        confirmed_appts = [a for a in appts if a["status"] == "Confirmed"]
        if confirmed_appts:
            cancel_opts = {
                f"#{a['id']} — {a['customer_name']} ({a['appointment_date']} {a['appointment_time']})": a["id"]
                for a in confirmed_appts
            }
            col_sel, col_btn = st.columns([3, 1])
            sel_cancel = col_sel.selectbox("Cancel an Appointment", list(cancel_opts.keys()))
            if col_btn.button("Cancel Selected", type="secondary", use_container_width=True):
                api_client.cancel_appointment(cancel_opts[sel_cancel])
                st.warning("Appointment cancelled.")
                st.rerun()
    else:
        st.caption("No appointments recorded yet.")
