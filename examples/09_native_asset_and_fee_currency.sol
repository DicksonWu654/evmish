// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20Like {
    function transferFrom(address from, address to, uint256 value) external returns (bool);
}

/// @notice Solidity transfer semantics and the meaning of the native balance
/// are chain-specific. A fixed transfer assumption can fail on a chain with a
/// wrapped, rebasing, or separately configured fee currency.
contract NativeTransferAssumption {
    function pay(address payable recipient) external payable {
        recipient.transfer(msg.value);
    }
}

/// @notice Make the asset choice explicit and use a checked low-level native
/// call. Fee currencies still need to be configured from the target chain.
contract ExplicitAssetVault {
    IERC20Like public immutable feeToken;
    bool private locked;

    modifier nonReentrant() {
        require(!locked, "reentrant");
        locked = true;
        _;
        locked = false;
    }

    constructor(address feeToken_) {
        feeToken = IERC20Like(feeToken_);
    }

    function payNative(address payable recipient, uint256 amount) external payable nonReentrant {
        require(msg.value == amount, "wrong native amount");
        (bool ok, ) = recipient.call{value: amount}("");
        require(ok, "native payment failed");
    }

    function payFeeToken(address recipient, uint256 amount) external nonReentrant returns (bool) {
        require(feeToken.transferFrom(msg.sender, recipient, amount), "fee token payment failed");
        return true;
    }
}
