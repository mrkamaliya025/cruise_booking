from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for
)

from database import get_db_connection

from pricing import calculate_price

import random
import string


app = Flask(__name__)


# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():

    return render_template("index.html")


# =====================================================
# SHOW CRUISES
# =====================================================

@app.route("/cruises")
def cruises():

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT
            cd.departure_id,
            c.cruise_line,
            c.ship,
            c.destination,
            cd.departure_date,
            cd.return_date,
            cd.nights,
            cd.adult_fare,
            cd.capacity,

            (
                cd.capacity -
                COALESCE(
                    (
                        SELECT SUM(o.total_passengers)
                        FROM orders o
                        WHERE o.departure_id = cd.departure_id
                        AND o.status = 'CONFIRMED'
                    ),
                    0
                )
            ) AS capacity_left

        FROM cruise_departures cd

        JOIN cruises c
        ON cd.cruise_id = c.cruise_id

        WHERE c.status = 'ACTIVE'
        AND cd.status = 'OPEN'

        ORDER BY cd.departure_date
    """

    cursor.execute(query)

    cruises_data = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "cruises.html",
        cruises=cruises_data
    )


# =====================================================
# BOOKING PAGE
# =====================================================

@app.route(
    "/book/<int:departure_id>",
    methods=["GET", "POST"]
)
def book(departure_id):

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    # Get cruise
    cursor.execute(
        """
        SELECT
            cd.*,
            c.cruise_line,
            c.ship,
            c.destination,

            (
                cd.capacity -
                COALESCE(
                    (
                        SELECT SUM(o.total_passengers)
                        FROM orders o
                        WHERE o.departure_id = cd.departure_id
                        AND o.status = 'CONFIRMED'
                    ),
                    0
                )
            ) AS capacity_left

        FROM cruise_departures cd

        JOIN cruises c
        ON cd.cruise_id = c.cruise_id

        WHERE cd.departure_id = %s
        """,
        (departure_id,)
    )

    cruise = cursor.fetchone()

    # Get services
    cursor.execute(
        """
        SELECT *
        FROM optional_services
        WHERE status = 'ACTIVE'
        """
    )

    services = cursor.fetchall()

    # Get promotions
    cursor.execute(
        """
        SELECT *
        FROM promotional_codes
        WHERE status = 'ACTIVE'
        """
    )

    promotions = cursor.fetchall()

    cursor.close()
    connection.close()

    if not cruise:

        return "Cruise departure not found", 404

    if request.method == "POST":

        customer_name = request.form["customer_name"]
        customer_email = request.form["customer_email"]
        customer_phone = request.form.get("customer_phone", "")

        # -----------------------------
        # Passenger ages
        # -----------------------------

        passenger_ages = []

        for i in range(1, 7):

            age = request.form.get(
                f"age_{i}"
            )

            if age:

                age = int(age)

                if age < 0:

                    return "Age cannot be negative."

                passenger_ages.append(age)

        if len(passenger_ages) == 0:

            return "At least one passenger is required."

        if len(passenger_ages) > 6:

            return "Maximum 6 passengers allowed."

        # -----------------------------
        # Capacity check
        # -----------------------------

        if len(passenger_ages) > cruise["capacity_left"]:

            return (
                f"Only {cruise['capacity_left']} "
                f"passengers are available."
            )

        # -----------------------------
        # Services
        # -----------------------------

        selected_service_ids = request.form.getlist(
            "services"
        )

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        selected_services = []

        if selected_service_ids:

            placeholders = ",".join(
                ["%s"] * len(selected_service_ids)
            )

            cursor.execute(
                f"""
                SELECT *
                FROM optional_services
                WHERE service_id IN ({placeholders})
                """,
                tuple(selected_service_ids)
            )

            selected_services = cursor.fetchall()

        # -----------------------------
        # Promotion
        # -----------------------------

        promotion = None

        promotion_code = (
            request.form
            .get("promotion_code", "")
            .strip()
            .upper()
        )

        promotion_error = None

        if promotion_code:

            cursor.execute(
                """
                SELECT *
                FROM promotional_codes
                WHERE code = %s
                AND status = 'ACTIVE'
                """,
                (promotion_code,)
            )

            promotion = cursor.fetchone()

            if not promotion:

                promotion_error = (
                    "Invalid promotional code."
                )

            else:

                today = date.today()

                if (
                    today < promotion["valid_from"]
                    or
                    today > promotion["valid_until"]
                ):

                    promotion_error = (
                        "Promotional code is outside "
                        "its valid date range."
                    )

                    promotion = None

        # -----------------------------
        # Calculate
        # -----------------------------

        if promotion_error:

            cursor.close()
            connection.close()

            return render_template(
                "booking.html",
                cruise=cruise,
                services=services,
                promotions=promotions,
                error=promotion_error
            )

        price = calculate_price(
            cruise["adult_fare"],
            cruise["nights"],
            passenger_ages,
            selected_services,
            promotion
        )

        # -----------------------------
        # Save customer
        # -----------------------------

        cursor.execute(
            """
            INSERT INTO customers
            (name, email, phone)
            VALUES (%s, %s, %s)
            """,
            (
                customer_name,
                customer_email,
                customer_phone
            )
        )

        customer_id = cursor.lastrowid

        # -----------------------------
        # Generate reference
        # -----------------------------

        reference = generate_reference()

        adult_count = sum(
            1
            for age in passenger_ages
            if age >= 18
        )

        child_count = (
            len(passenger_ages)
            - adult_count
        )

        # -----------------------------
        # Save order
        # -----------------------------

        promotion_id = (
            promotion["promotion_id"]
            if promotion
            else None
        )

        cursor.execute(
            """
            INSERT INTO orders
            (
                order_reference,
                customer_id,
                departure_id,
                adult_count,
                child_count,
                total_passengers,
                base_fare,
                group_discount,
                promotion_discount,
                services_total,
                subtotal,
                tax_rate,
                tax_amount,
                final_amount,
                promotion_id
            )

            VALUES
            (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            """,

            (
                reference,
                customer_id,
                departure_id,
                adult_count,
                child_count,
                len(passenger_ages),
                price["base_fare"],
                price["group_discount"],
                price["promotion_discount"],
                price["services_total"],
                price["subtotal"],
                price["tax_rate"],
                price["tax_amount"],
                price["final_amount"],
                promotion_id
            )
        )

        order_id = cursor.lastrowid

        # -----------------------------
        # Save passengers
        # -----------------------------

        for passenger in price["passenger_fares"]:

            age = passenger["age"]

            passenger_type = (
                "ADULT"
                if age >= 18
                else "CHILD"
            )

            cursor.execute(
                """
                INSERT INTO passengers
                (
                    order_id,
                    name,
                    age,
                    passenger_type,
                    fare_percentage,
                    fare_amount
                )

                VALUES
                (%s, %s, %s, %s, %s, %s)
                """,

                (
                    order_id,
                    f"Passenger {len(passenger_ages)}",
                    age,
                    passenger_type,
                    passenger["percentage"],
                    passenger["fare"]
                )
            )

        # -----------------------------
        # Save services
        # -----------------------------

        for service in price["service_details"]:

            cursor.execute(
                """
                INSERT INTO order_services
                (
                    order_id,
                    service_id,
                    quantity,
                    unit_price,
                    total_price
                )

                VALUES
                (%s, %s, %s, %s, %s)
                """,

                (
                    order_id,
                    service["service_id"],
                    service["quantity"],
                    service["unit_price"],
                    service["total"]
                )
            )

        # -----------------------------
        # Promotion redemption
        # -----------------------------

        if promotion:

            cursor.execute(
                """
                SELECT COUNT(*) AS usage_count

                FROM promotion_redemptions pr

                WHERE pr.promotion_id = %s
                AND pr.customer_id = %s
                """,

                (
                    promotion["promotion_id"],
                    customer_id
                )
            )

            usage = cursor.fetchone()

            if (
                usage["usage_count"]
                >= promotion["max_uses_per_customer"]
            ):

                connection.rollback()

                cursor.close()
                connection.close()

                return (
                    "You have reached the maximum "
                    "usage limit for this promotion."
                )

            cursor.execute(
                """
                INSERT INTO promotion_redemptions
                (
                    promotion_id,
                    customer_id,
                    order_id,
                    discount_amount
                )

                VALUES
                (%s, %s, %s, %s)
                """,

                (
                    promotion["promotion_id"],
                    customer_id,
                    order_id,
                    price["promotion_discount"]
                )
            )

        # -----------------------------
        # Historical pricing
        # -----------------------------

        cursor.execute(
            """
            INSERT INTO order_pricing
            (
                order_id,
                adult_fare,
                nights,
                group_discount_rate,
                group_discount_amount,
                promotion_code,
                promotion_type,
                promotion_value,
                promotion_discount_amount,
                services_total,
                tax_rate,
                tax_amount,
                subtotal,
                final_amount
            )

            VALUES
            (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            """,

            (
                order_id,
                cruise["adult_fare"],
                cruise["nights"],
                price["group_rate"],
                price["group_discount"],

                promotion["code"]
                if promotion else None,

                promotion["discount_type"]
                if promotion else None,

                promotion["discount_value"]
                if promotion else None,

                price["promotion_discount"],

                price["services_total"],

                price["tax_rate"],
                price["tax_amount"],

                price["subtotal"],
                price["final_amount"]
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        return render_template(
            "confirmation.html",
            reference=reference,
            price=price,
            cruise=cruise,
            customer_name=customer_name
        )

    cursor.close()
    connection.close()

    return render_template(
        "booking.html",
        cruise=cruise,
        services=services,
        promotions=promotions
    )


# =====================================================
# BOOKINGS
# =====================================================

@app.route("/bookings")
def bookings():

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            o.order_reference,
            c.name AS customer_name,
            cr.ship,
            cr.destination,
            cd.departure_date,
            o.total_passengers,
            o.final_amount,
            o.status

        FROM orders o

        JOIN customers c
        ON o.customer_id = c.customer_id

        JOIN cruise_departures cd
        ON o.departure_id = cd.departure_id

        JOIN cruises cr
        ON cd.cruise_id = cr.cruise_id

        ORDER BY o.created_at DESC
        """
    )

    data = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "bookings.html",
        bookings=data
    )


# =====================================================
# REFERENCE GENERATOR
# =====================================================

def generate_reference():

    characters = (
        string.ascii_uppercase
        + string.digits
    )

    random_part = "".join(
        random.choices(
            characters,
            k=8
        )
    )

    return "CRZ-" + random_part


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )