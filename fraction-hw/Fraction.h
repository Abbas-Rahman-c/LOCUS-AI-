#ifndef FRACTION_H
#define FRACTION_H

#include <iostream>

namespace cs_fraction {

class Fraction {
public:
    // Pre: The denominator must not be 0.
    // Post: A Fraction is created with the given numerator and denominator
    //       (defaults create 0/1). The Fraction is stored in reduced form.
    Fraction(int inNumerator = 0, int inDenominator = 1);

    // Pre: None.
    // Post: The Fraction has been printed to out in reduced form as a whole
    //       number, proper fraction, or mixed number (with a leading minus
    //       if negative).
    friend std::ostream& operator<<(std::ostream& out, const Fraction& f);

    // Pre: The stream contains a Fraction in a valid format with no spaces
    //      (whole number, fraction, or mixed number; may be negative).
    // Post: readMe has been set to the Fraction read from in, in reduced form.
    friend std::istream& operator>>(std::istream& in, Fraction& readMe);

    // Pre: None.
    // Post: Returns true if left is less than right; false otherwise.
    friend bool operator<(const Fraction& left, const Fraction& right);

    // Pre: None.
    // Post: Returns true if left is less than or equal to right; false otherwise.
    friend bool operator<=(const Fraction& left, const Fraction& right);

    // Pre: None.
    // Post: Returns true if left is greater than right; false otherwise.
    friend bool operator>(const Fraction& left, const Fraction& right);

    // Pre: None.
    // Post: Returns true if left is greater than or equal to right; false otherwise.
    friend bool operator>=(const Fraction& left, const Fraction& right);

    // Pre: None.
    // Post: Returns true if left equals right; false otherwise.
    friend bool operator==(const Fraction& left, const Fraction& right);

    // Pre: None.
    // Post: Returns true if left does not equal right; false otherwise.
    friend bool operator!=(const Fraction& left, const Fraction& right);

    // Pre: None.
    // Post: Returns the sum of left and right, in reduced form.
    friend Fraction operator+(const Fraction& left, const Fraction& right);

    // Pre: None.
    // Post: Returns the difference of left and right, in reduced form.
    friend Fraction operator-(const Fraction& left, const Fraction& right);

    // Pre: None.
    // Post: Returns the product of left and right, in reduced form.
    friend Fraction operator*(const Fraction& left, const Fraction& right);

    // Pre: right must not be equal to 0.
    // Post: Returns the quotient of left and right, in reduced form.
    friend Fraction operator/(const Fraction& left, const Fraction& right);

    // Pre: None.
    // Post: Adds right to this Fraction; returns a reference to this Fraction.
    Fraction& operator+=(const Fraction& right);

    // Pre: None.
    // Post: Subtracts right from this Fraction; returns a reference to this Fraction.
    Fraction& operator-=(const Fraction& right);

    // Pre: None.
    // Post: Multiplies this Fraction by right; returns a reference to this Fraction.
    Fraction& operator*=(const Fraction& right);

    // Pre: right must not be equal to 0.
    // Post: Divides this Fraction by right; returns a reference to this Fraction.
    Fraction& operator/=(const Fraction& right);

    // Pre: None.
    // Post: Increments this Fraction by 1 and returns a reference to it.
    Fraction& operator++();

    // Pre: None.
    // Post: Increments this Fraction by 1 and returns a copy of its old value.
    Fraction operator++(int);

    // Pre: None.
    // Post: Decrements this Fraction by 1 and returns a reference to it.
    Fraction& operator--();

    // Pre: None.
    // Post: Decrements this Fraction by 1 and returns a copy of its old value.
    Fraction operator--(int);

private:
    int numerator;
    int denominator;

    // Pre: None.
    // Post: This Fraction is stored in reduced form with a non-negative
    //       denominator. If the numerator is 0, the denominator is 1.
    void simplify();
};

}

#endif
