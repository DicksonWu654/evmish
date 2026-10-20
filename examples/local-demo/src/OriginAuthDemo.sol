// SPDX-License-Identifier: MIT
pragma solidity 0.8.36;

/// @notice The vulnerable pattern: an intermediate contract can act while the
/// owner is the transaction origin. The account-code probes show why origin and
/// code-shape assumptions are especially brittle across EVM ecosystems.
contract OriginWallet {
    address public immutable owner;

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    function withdraw(address payable recipient, uint256 amount) external {
        require(tx.origin == owner, "origin owner");
        (bool ok, ) = recipient.call{value: amount}("");
        require(ok, "payment failed");
    }
}

/// @notice The safe baseline authorizes the explicit calling principal.
contract PrincipalWallet {
    address public immutable owner;

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    function withdraw(address payable recipient, uint256 amount) external {
        require(msg.sender == owner, "principal owner");
        (bool ok, ) = recipient.call{value: amount}("");
        require(ok, "payment failed");
    }
}

contract OriginPhishingContract {
    receive() external payable {}

    function drain(OriginWallet wallet, uint256 amount) external {
        wallet.withdraw(payable(address(this)), amount);
    }

    function drainPrincipal(PrincipalWallet wallet, uint256 amount) external {
        wallet.withdraw(payable(address(this)), amount);
    }
}
