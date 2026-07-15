#include "Fraction.h"
#include <cassert>
#include <iostream>
using namespace std;

namespace cs_fraction {

Fraction::Fraction(int inNumerator, int inDenominator) {
    assert(inDenominator != 0);
    numerator = inNumerator;
    denominator = inDenominator;
    simplify();
}






ostream& operator<<(ostream& out, const Fraction& f) {
    int n = f.numerator;
    int d = f.denominator;

    if (n < 0) {
        out << "-";
        n = -n;
    }

    if (d == 1) {
        out << n;
    } else if (n < d) {
        out << n << "/" << d;
    } else {
        out << (n / d) << "+" << (n % d) << "/" << d;
    }

    return out;
}






istream& operator>>(istream& in, Fraction& readMe) {
    int temp;
    in >> temp;

    if (in.peek() == '+') {
        in.ignore();
        int num;
        int den;
        in >> num;
        in.ignore();
        in >> den;

        if (temp >= 0) {
            readMe.numerator = temp * den + num;
        } else {
            readMe.numerator = temp * den - num;
        }
        readMe.denominator = den;
    } else if (in.peek() == '/') {
        in.ignore();
        int den;
        in >> den;
        readMe.numerator = temp;
        readMe.denominator = den;
    } else {
        readMe.numerator = temp;
        readMe.denominator = 1;
    }

    readMe.simplify();
    return in;
}






bool operator<(const Fraction& left, const Fraction& right) {
    return left.numerator * right.denominator < right.numerator * left.denominator;
}


bool operator<=(const Fraction& left, const Fraction& right) {
    return left < right || left == right;
}


bool operator>(const Fraction& left, const Fraction& right) {
    return right < left;
}


bool operator>=(const Fraction& left, const Fraction& right) {
    return right < left || left == right;
}


bool operator==(const Fraction& left, const Fraction& right) {
    return left.numerator * right.denominator == right.numerator * left.denominator;
}


bool operator!=(const Fraction& left, const Fraction& right) {
    return !(left == right);
}






Fraction operator+(const Fraction& left, const Fraction& right) {
    return Fraction(left.numerator * right.denominator + right.numerator * left.denominator,
                    left.denominator * right.denominator);
}


Fraction operator-(const Fraction& left, const Fraction& right) {
    return Fraction(left.numerator * right.denominator - right.numerator * left.denominator,
                    left.denominator * right.denominator);
}


Fraction operator*(const Fraction& left, const Fraction& right) {
    return Fraction(left.numerator * right.numerator,
                    left.denominator * right.denominator);
}


Fraction operator/(const Fraction& left, const Fraction& right) {
    return Fraction(left.numerator * right.denominator,
                    left.denominator * right.numerator);
}






Fraction& Fraction::operator+=(const Fraction& right) {
    *this = *this + right;
    return *this;
}


Fraction& Fraction::operator-=(const Fraction& right) {
    *this = *this - right;
    return *this;
}


Fraction& Fraction::operator*=(const Fraction& right) {
    *this = *this * right;
    return *this;
}


Fraction& Fraction::operator/=(const Fraction& right) {
    *this = *this / right;
    return *this;
}






Fraction& Fraction::operator++() {
    *this += 1;
    return *this;
}


Fraction Fraction::operator++(int) {
    Fraction temp(*this);
    *this += 1;
    return temp;
}


Fraction& Fraction::operator--() {
    *this -= 1;
    return *this;
}


Fraction Fraction::operator--(int) {
    Fraction temp(*this);
    *this -= 1;
    return temp;
}






void Fraction::simplify() {
    if (numerator == 0) {
        denominator = 1;
        return;
    }

    if (denominator < 0) {
        numerator = -numerator;
        denominator = -denominator;
    }

    int a = numerator;
    if (a < 0) {
        a = -a;
    }
    int b = denominator;

    int limit;
    if (a < b) {
        limit = a;
    } else {
        limit = b;
    }

    int gcf = 1;
    for (int i = 1; i <= limit; i++) {
        if (a % i == 0 && b % i == 0) {
            gcf = i;
        }
    }

    numerator = numerator / gcf;
    denominator = denominator / gcf;
}

}
